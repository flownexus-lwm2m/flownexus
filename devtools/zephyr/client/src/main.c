/*
 * Copyright (c) 2017 Linaro Limited
 * Copyright (c) 2017-2019 Foundries.io
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/conn_mgr_monitor.h>
#include <zephyr/net/lwm2m.h>
#include <zephyr/net/net_if.h>
#include <zephyr/sys/util.h>

#include "app.h"

LOG_MODULE_REGISTER(app_main, LOG_LEVEL_INF);

#define L4_EVENT_MASK (NET_EVENT_L4_CONNECTED | NET_EVENT_L4_DISCONNECTED)

static struct lwm2m_ctx client_ctx;
static struct net_mgmt_event_callback l4_cb;

static void rd_client_event(struct lwm2m_ctx *client, enum lwm2m_rd_client_event event)
{
	switch (event) {
	case LWM2M_RD_CLIENT_EVENT_REGISTRATION_COMPLETE:
		LOG_INF("Registration complete");
		break;
	case LWM2M_RD_CLIENT_EVENT_REG_UPDATE_COMPLETE:
		LOG_INF("Registration update complete");
		break;
	case LWM2M_RD_CLIENT_EVENT_REGISTRATION_FAILURE:
		LOG_WRN("Registration failure");
		break;
	case LWM2M_RD_CLIENT_EVENT_DEREGISTER:
		LOG_INF("Deregistered");
		break;
	case LWM2M_RD_CLIENT_EVENT_DISCONNECT:
		LOG_INF("Disconnected");
		break;
	case LWM2M_RD_CLIENT_EVENT_NETWORK_ERROR:
		LOG_ERR("Network error");
		break;
	default:
		LOG_DBG("RD client event %d", event);
		break;
	}
}

static void observe_cb(enum lwm2m_observe_event event, struct lwm2m_obj_path *path,
		       void *user_data)
{
	char buf[LWM2M_MAX_PATH_STR_SIZE];

	switch (event) {
	case LWM2M_OBSERVE_EVENT_OBSERVER_ADDED:
		LOG_INF("Observer added for %s", lwm2m_path_log_buf(buf, path));
		break;
	case LWM2M_OBSERVE_EVENT_OBSERVER_REMOVED:
		LOG_INF("Observer removed for %s", lwm2m_path_log_buf(buf, path));
		break;
	case LWM2M_OBSERVE_EVENT_NOTIFY_TIMEOUT:
		LOG_INF("Notify timeout for %s, trying registration update",
			lwm2m_path_log_buf(buf, path));
		lwm2m_rd_client_update();
		break;
	default:
		break;
	}
}

static void l4_event_handler(struct net_mgmt_event_callback *cb, uint64_t event,
			     struct net_if *iface)
{
	if (event == NET_EVENT_L4_CONNECTED) {
		LOG_INF("Network up");
		lwm2m_engine_resume();
	} else if (event == NET_EVENT_L4_DISCONNECTED) {
		LOG_INF("Network down");
		lwm2m_engine_pause();
	}
}

int app_lwm2m_start(const char *endpoint)
{
	uint32_t flags = IS_ENABLED(CONFIG_LWM2M_RD_CLIENT_SUPPORT_BOOTSTRAP)
				 ? LWM2M_RD_CLIENT_FLAG_BOOTSTRAP
				 : 0;

	return lwm2m_rd_client_start(&client_ctx, endpoint, flags, rd_client_event, observe_cb);
}

static int security_obj_init(void)
{
	lwm2m_set_string(&LWM2M_OBJ(0, 0, 0), CONFIG_LWM2M_APP_SERVER);
	lwm2m_set_u8(&LWM2M_OBJ(0, 0, 2), IS_ENABLED(CONFIG_LWM2M_DTLS_SUPPORT) ? 0 : 3);

#if defined(CONFIG_LWM2M_DTLS_SUPPORT)
	char psk[1 + sizeof(CONFIG_LWM2M_APP_PSK) / 2];
	size_t len = hex2bin(CONFIG_LWM2M_APP_PSK, sizeof(CONFIG_LWM2M_APP_PSK) - 1, psk,
			     sizeof(psk));

	if (len == 0) {
		return -EINVAL;
	}
	lwm2m_set_string(&LWM2M_OBJ(0, 0, 3), CONFIG_LWM2M_APP_ID);
	lwm2m_set_opaque(&LWM2M_OBJ(0, 0, 5), psk, len);
#endif

#if defined(CONFIG_LWM2M_RD_CLIENT_SUPPORT_BOOTSTRAP)
	lwm2m_set_u8(&LWM2M_OBJ(0, 0, 1), 1);
	lwm2m_create_object_inst(&LWM2M_OBJ(0, 1));
#else
	lwm2m_set_u16(&LWM2M_OBJ(0, 0, 10), CONFIG_LWM2M_SERVER_DEFAULT_SSID);
	lwm2m_set_u16(&LWM2M_OBJ(1, 0, 0), CONFIG_LWM2M_SERVER_DEFAULT_SSID);
#endif
	return 0;
}

static int network_init(void)
{
	struct net_if *iface = net_if_get_default();
	int ret;

	if (iface == NULL) {
		return -ENODEV;
	}

	net_mgmt_init_event_callback(&l4_cb, l4_event_handler, L4_EVENT_MASK);
	net_mgmt_add_event_callback(&l4_cb);

	ret = net_if_up(iface);
	if (ret < 0 && ret != -EALREADY) {
		return ret;
	}

	return conn_mgr_if_connect(iface);
}

int main(void)
{
	int ret;

	ret = network_init();
	if (ret < 0) {
		LOG_ERR("Network init failed (%d)", ret);
		return ret;
	}

	ret = security_obj_init();
	if (ret == 0) {
		ret = device_obj_init();
	}
	if (ret == 0) {
		ret = sensors_obj_init();
	}
	if (ret < 0) {
		LOG_ERR("LwM2M object setup failed (%d)", ret);
		return ret;
	}

#if defined(CONFIG_LWM2M_DTLS_SUPPORT)
	client_ctx.tls_tag = CONFIG_LWM2M_APP_TLS_TAG;
#endif

	if (IS_ENABLED(CONFIG_LWM2M_APP_AUTOSTART)) {
		ret = app_lwm2m_start(CONFIG_LWM2M_APP_ID);
		if (ret < 0) {
			LOG_ERR("RD client start failed (%d)", ret);
			return ret;
		}
	}

	LOG_INF("Client initialized");
	return 0;
}
