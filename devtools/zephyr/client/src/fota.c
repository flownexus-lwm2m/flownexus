/*
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/lwm2m.h>

#include "app.h"

LOG_MODULE_REGISTER(app_fota, LOG_LEVEL_INF);

static int report(bool with_result)
{
	struct lwm2m_ctx *ctx = lwm2m_rd_client_ctx();
	const struct lwm2m_obj_path paths[] = {
		LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 3),
		LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 5),
	};

	if (ctx == NULL) {
		return -ENOTCONN;
	}

	return lwm2m_send_cb(ctx, paths, with_result ? 2 : 1, NULL);
}

static void report_updating(struct k_work *work)
{
	int ret = report(false);

	if (ret < 0) {
		LOG_ERR("Cannot report update state (%d)", ret);
	}
}

static K_WORK_DEFINE(updating_work, report_updating);

static int package_uri_cb(uint16_t obj_inst_id, uint16_t res_id, uint16_t res_inst_id,
			  uint8_t *data, uint16_t data_len, bool last_block, size_t total_size,
			  size_t offset)
{
	LOG_INF("write 5/0/1=%.*s", data_len, (char *)data);
	return 0;
}

static int update_cb(uint16_t obj_inst_id, uint8_t *args, uint16_t args_len)
{
	LOG_INF("execute 5/0/2 (update)");
	k_work_submit(&updating_work);
	return 0;
}

int fota_set_state(uint8_t state)
{
	int ret = lwm2m_set_u8(&LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 3), state);

	return ret < 0 ? ret : report(false);
}

int fota_set_result(uint8_t result)
{
	int ret = lwm2m_set_u8(&LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 3), STATE_IDLE);

	if (ret == 0) {
		ret = lwm2m_set_u8(&LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 5), result);
	}
	return ret < 0 ? ret : report(true);
}

int fota_obj_init(void)
{
	lwm2m_firmware_set_update_cb(update_cb);
	return lwm2m_register_post_write_callback(&LWM2M_OBJ(LWM2M_OBJECT_FIRMWARE_ID, 0, 1),
						  package_uri_cb);
}
