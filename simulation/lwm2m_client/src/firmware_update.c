/*
 * Copyright (c) 2022 Nordic Semiconductor
 * Copyright (c) 2024 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_MODULE_NAME app_fw_update
#define LOG_LEVEL LOG_LEVEL_INF

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(LOG_MODULE_NAME, LOG_LEVEL);

#include <zephyr/net/lwm2m.h>
#include "lwm2m_engine.h"
#include <sys/socket.h>
#include <zephyr/net/http/client.h>
#include "modules.h"
#include <ctype.h>

#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
#include <zephyr/net/tls_credentials.h>
#include "ca_certificate.h"
#endif

#define MAX_URL_LENGTH 256

const char *host;
const char *port;
static char download_url[MAX_URL_LENGTH];
static char response[CONFIG_NET_BUF_DATA_SIZE];
unsigned int cur_bytes;

static struct lwm2m_ctx *client_ctx;

#define SSTRLEN(s) (sizeof(s) - 1)

static ssize_t sendall(int sock, const void *buf, size_t len)
{
	while (len) {
		ssize_t out_len = send(sock, buf, len, 0);
		if (out_len < 0) {
			return out_len;
		}
		buf = (const char *)buf + out_len;
		len -= out_len;
	}

	return 0;
}

static int parse_status(bool *redirect)
{
	char *ptr;
	int code;

	ptr = strstr(response, "HTTP");
	if (ptr == NULL) {
		return -1;
	}

	ptr = strstr(response, " ");
	if (ptr == NULL) {
		return -1;
	}

	ptr++;

	code = atoi(ptr);
	if (code >= 300 && code < 400) {
		*redirect = true;
	}

	return 0;
}

static int parse_header(bool *location_found)
{
	char *ptr;

	ptr = strstr(response, ":");
	if (ptr == NULL) {
		return 0;
	}

	*ptr = '\0';
	ptr = response;

	while (*ptr != '\0') {
		*ptr = tolower(*ptr);
		ptr++;
	}

	if (strcmp(response, "location") != 0) {
		return 0;
	}

	/* Skip whitespace */
	while (*(++ptr) == ' ') {
		;
	}

	strncpy(download_url, ptr, sizeof(download_url));
	download_url[sizeof(download_url) - 1] = '\0';

	/* Trim LF. */
	ptr = strstr(download_url, "\n");
	if (ptr == NULL) {
		printf("Redirect URL too long or malformed\n");
		return -1;
	}

	*ptr = '\0';

	/* Trim CR if present. */
	ptr = strstr(download_url, "\r");
	if (ptr != NULL) {
		*ptr = '\0';
	}

	*location_found = true;

	return 0;
}

static int skip_headers(int sock)
{
	int state = 0;
	int i = 0;
	bool status_line = true;
	bool redirect_code = false;
	bool location_found = false;

	while (1) {
		int st;

		st = recv(sock, response + i, 1, 0);
		if (st <= 0) {
			return st;
		}
		LOG_DBG("Received %c", response[i]);

		if (state == 0 && response[i] == '\r') {
			state++;
		} else if ((state == 0 || state == 1) && response[i] == '\n') {
			state = 2;
			response[i + 1] = '\0';
			i = 0;

			if (status_line) {
				if (parse_status(&redirect_code) < 0) {
					return -1;
				}

				status_line = false;
			} else {
				if (parse_header(&location_found) < 0) {
					return -1;
				}
			}

			continue;
		} else if (state == 2 && response[i] == '\r') {
			state++;
		} else if ((state == 2 || state == 3) && response[i] == '\n') {
			break;
		} else {
			state = 0;
		}

		i++;
		if (i >= sizeof(response) - 1) {
			i = 0;
		}
	}

	return 1;
}

static int download(char *host, char *path)
{
	static struct addrinfo hints;
	struct addrinfo *res;
	int sock;
	int resolve_attempts = 10;
	int ret;
	bool is_tls = false;

	if (strncmp(host, "http://", SSTRLEN("http://")) == 0) {
		port = "8000";
		host += SSTRLEN("http://");
#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
	} else if (strncmp(host, "https://",
		   SSTRLEN("https://")) == 0) {
		is_tls = true;
		port = "443";
		host += SSTRLEN("https://");
#endif /* defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS) */
	} else {
		LOG_ERR("Only http: "
#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
		      "and https: "
#endif
		      "URLs are supported");
		return -EINVAL;
	}

	LOG_INF("HTTP GET request for http%s://%s:%s%s",
	       (is_tls ? "s" : ""), host, port, path);

	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;

	while (resolve_attempts--) {
		ret = getaddrinfo(host, port, &hints, &res);
		if (ret == 0) {
			break;
		}

		LOG_ERR("getaddrinfo status: %d, retrying\n", ret);
		k_sleep(K_MSEC(1000));
	}
	if (ret != 0) {
		LOG_ERR("Unable to resolve address");
		return -ETIMEDOUT;
	}

	cur_bytes = 0U;

	if (is_tls) {
#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
		sock = socket(res->ai_family, res->ai_socktype, IPPROTO_TLS_1_2);
#else
		LOG_ERR("TLS not supported\n");
		return -ENOTSUP;
#endif
	} else {
		sock = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
	}

	if (sock < 0) {
		LOG_ERR("Failed to create socket %d", sock);
		return -ENOTCONN;
	}

#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
	if (is_tls) {
		LOG_INF("Setting up TLS parameters");
		sec_tag_t sec_tag_opt[ARRAY_SIZE(ca_certificates)];

		for (int i = 0; i < ARRAY_SIZE(ca_certificates); i++) {
			sec_tag_opt[i] = CA_CERTIFICATE_TAG + i;
		};

		ret = setsockopt(sock, SOL_TLS, TLS_SEC_TAG_LIST,
				 sec_tag_opt, sizeof(sec_tag_opt));
		if (ret < 0) {
			LOG_ERR("Failed to set TLS_SEC_TAG_LIST option");
			goto error;
		}

		ret = setsockopt(sock, SOL_TLS, TLS_HOSTNAME, host, strlen(host) + 1);
		if (ret < 0) {
			LOG_ERR("Failed to set TLS_HOSTNAME option");
			goto error;
		}
		LOG_INF("TLS HOSTNAME set to %s", host);
		LOG_INF("TLS SEC TAG LIST set to %d", sec_tag_opt[0]);
		LOG_INF("Connecting to %s:%s", host, port);
	}
#endif
	ret = connect(sock, res->ai_addr, res->ai_addrlen);
	if (ret < 0) {
		LOG_ERR("Failed to connect to server");
		goto error;
	}
	sendall(sock, "GET /", SSTRLEN("GET /"));
	sendall(sock, path, strlen(path));
	sendall(sock, " HTTP/1.0\r\n", SSTRLEN(" HTTP/1.0\r\n"));
	sendall(sock, "Host: ", SSTRLEN("Host: "));
	sendall(sock, host, strlen(host));
	sendall(sock, "\r\n\r\n", SSTRLEN("\r\n\r\n"));

	if (skip_headers(sock) <= 0) {
		LOG_ERR("EOF or error in response headers");
		ret = -EINVAL;
		goto error;
	}

	while (1) {
		LOG_INF("Receiving data");
		int len = recv(sock, response, sizeof(response) - 1, 0);

		if (len < 0) {
			if (errno == EAGAIN || errno == EWOULDBLOCK) {
				LOG_ERR("Timeout on reading response");
				ret = -errno;
			} else {
				LOG_ERR("Error reading response");
				ret = -errno;
			}
			goto error;
		}

		if (len == 0) {
			LOG_INF("EOF on response");
			break;
		}

		cur_bytes += len;
		LOG_INF("Downloaded %u Bytes", cur_bytes);

		response[len] = 0;
	}

error:
	(void)close(sock);

	return ret;
}

static int firmware_update_cb(uint16_t obj_inst_id,
			      uint8_t *args, uint16_t args_len)
{
	LOG_INF("FIRMWARE: UPDATE");

	/* TODO: kick off update process */

	/* If success, set the update result as RESULT_SUCCESS.
	 * In reality, it should be set at function lwm2m_setup()
	 */
	lwm2m_firmware_set_update_result(RESULT_SUCCESS);
	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 3), 1, NULL);
	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 5), 1, NULL);
	return 0;
}

static int firmware_download_cb(uint16_t obj_inst_id,
				uint16_t res_id, uint16_t res_inst_id,
				uint8_t *data, uint16_t data_len,
				bool last_block, size_t total_size, size_t offset)
{
	int ret;

	LOG_INF("FIRMWARE: DOWNLOAD");
	LOG_INF("Download Link: %s", data);

	lwm2m_firmware_set_update_state(STATE_DOWNLOADING);
	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 3), 1, NULL);

	/* download is a blocking method */
	ret = download(CONFIG_DL_SERVER_HOSTNAME, data);
	if (ret == 0) {
		lwm2m_firmware_set_update_state(STATE_DOWNLOADED);
		lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 3), 1, NULL);
		return 0;
	}

	LOG_ERR("Download failed with %d", ret);
	switch (ret) {
		case -ENOTSUP:
		case -EINVAL:
		lwm2m_firmware_set_update_result(RESULT_UNSUP_PROTO);
		lwm2m_firmware_set_update_state(STATE_IDLE);
		break;
		case -ENOTCONN:
		lwm2m_firmware_set_update_result(RESULT_CONNECTION_LOST);
		lwm2m_firmware_set_update_state(STATE_IDLE);
		break;
		default:
		lwm2m_firmware_set_update_result(RESULT_UPDATE_FAILED);
		lwm2m_firmware_set_update_state(STATE_IDLE);
	}

	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 3), 1, NULL);
	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 5), 1, NULL);

	return ret;
}

static int firmware_cancel_cb(const uint16_t obj_inst_id)
{
	LOG_INF("FIRMWARE: Update canceled");

	lwm2m_firmware_set_update_state(STATE_IDLE);
	lwm2m_firmware_set_update_result(RESULT_UPDATE_FAILED);

	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 3), 1, NULL);
	lwm2m_send_cb(client_ctx, &LWM2M_OBJ(5, 0, 5), 1, NULL);

	return 0;
}

void init_firmware_update(struct lwm2m_ctx *client)
{
	int ret;

	client_ctx = client;

#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
	LOG_INF("Adding CA certificate");
	for (int i = 0; i < ARRAY_SIZE(ca_certificates); i++) {
		ret = tls_credential_add(CA_CERTIFICATE_TAG + i,
				   TLS_CREDENTIAL_CA_CERTIFICATE,
				   ca_certificates[i],
				   strlen(ca_certificates[i]) + 1);
		if (ret < 0) {
			LOG_ERR("Failed to add CA certificate %d", i);
			return;
		}
	}
#endif
	/* setup data buffer for block-wise transfer */
	lwm2m_register_post_write_callback(&LWM2M_OBJ(5, 0, 1), firmware_download_cb);

	lwm2m_firmware_set_cancel_cb(firmware_cancel_cb);
	lwm2m_firmware_set_update_cb(firmware_update_cb);
}
