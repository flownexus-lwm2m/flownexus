/*
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdlib.h>

#include <zephyr/net/conn_mgr_connectivity.h>
#include <zephyr/net/lwm2m.h>
#include <zephyr/net/net_if.h>
#include <zephyr/shell/shell.h>

#include "app.h"

static int cmd_start(const struct shell *sh, size_t argc, char **argv)
{
	const char *endpoint = argc > 1 ? argv[1] : CONFIG_LWM2M_APP_ID;
	int ret = 0;

	if (argc > 2) {
		ret = lwm2m_set_string(&LWM2M_OBJ(0, 0, 0), argv[2]);
	}
	if (ret == 0) {
		ret = app_lwm2m_start(endpoint);
	}
	if (ret < 0) {
		shell_error(sh, "start failed: %d", ret);
	}
	return ret;
}

static int cmd_net_up(const struct shell *sh, size_t argc, char **argv)
{
	int ret = conn_mgr_if_connect(net_if_get_default());

	if (ret < 0) {
		shell_error(sh, "net up failed: %d", ret);
	}
	return ret;
}

static int cmd_net_down(const struct shell *sh, size_t argc, char **argv)
{
	int ret = conn_mgr_if_disconnect(net_if_get_default());

	if (ret < 0) {
		shell_error(sh, "net down failed: %d", ret);
	}
	return ret;
}

static int fota_cmd(const struct shell *sh, const char *arg, unsigned long max,
		    int (*set)(uint8_t))
{
	char *end;
	unsigned long value = strtoul(arg, &end, 10);
	int ret;

	if (*end != '\0' || value > max) {
		shell_error(sh, "invalid value: %s", arg);
		return -EINVAL;
	}

	ret = set(value);
	if (ret < 0) {
		shell_error(sh, "report failed: %d", ret);
	}
	return ret;
}

static int cmd_fota_state(const struct shell *sh, size_t argc, char **argv)
{
	return fota_cmd(sh, argv[1], STATE_UPDATING, fota_set_state);
}

static int cmd_fota_result(const struct shell *sh, size_t argc, char **argv)
{
	return fota_cmd(sh, argv[1], RESULT_UNSUP_PROTO, fota_set_result);
}

SHELL_STATIC_SUBCMD_SET_CREATE(sub_net,
	SHELL_CMD_ARG(up, NULL, "Connect the default interface", cmd_net_up, 1, 0),
	SHELL_CMD_ARG(down, NULL, "Disconnect the default interface", cmd_net_down, 1, 0),
	SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(sub_fota,
	SHELL_CMD_ARG(state, NULL, "state <0-3>\nSet and send Firmware Update state 5/0/3",
		      cmd_fota_state, 2, 0),
	SHELL_CMD_ARG(result, NULL, "result <0-9>\nSet and send update result 5/0/5",
		      cmd_fota_result, 2, 0),
	SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(sub_flownexus,
	SHELL_CMD_ARG(start, NULL, "start [endpoint [server-uri]]\nStart the RD client",
		      cmd_start, 1, 2),
	SHELL_CMD(net, &sub_net, "Simulate network loss and recovery", NULL),
	SHELL_CMD(fota, &sub_fota, "Simulate a firmware update", NULL),
	SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(flownexus, &sub_flownexus, "Flownexus client commands", NULL);
