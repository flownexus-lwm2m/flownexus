/*
 * Copyright (c) 2017 Linaro Limited
 * Copyright (c) 2017-2019 Foundries.io
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/logging/log.h>
#include <zephyr/net/lwm2m.h>

#include "app.h"

LOG_MODULE_REGISTER(app_device, LOG_LEVEL_INF);

#define MANUFACTURER "Zephyr"
#define MODEL_NUMBER "Flownexus Client"
#define SERIAL_NUMBER "345000123"
#define FIRMWARE_VER "1.0"
#define HARDWARE_VER "1.0.1"

static uint8_t bat_level = 95;
static uint8_t bat_status = LWM2M_DEVICE_BATTERY_STATUS_CHARGING;
static uint8_t pwr_src = LWM2M_DEVICE_PWR_SRC_TYPE_USB;
static int pwr_mv = 5000;
static int pwr_ma = 900;
static int mem_free = 15;
static int mem_total = 25;
static char utc_offset[16] = "+00:00";

static int reboot_cb(uint16_t obj_inst_id, uint8_t *args, uint16_t args_len)
{
	LOG_INF("execute 3/0/4 (reboot)");
	return 0;
}

static int factory_default_cb(uint16_t obj_inst_id, uint8_t *args, uint16_t args_len)
{
	LOG_INF("execute 3/0/5 (factory default)");
	return 0;
}

static int utc_offset_cb(uint16_t obj_inst_id, uint16_t res_id, uint16_t res_inst_id,
			 uint8_t *data, uint16_t data_len, bool last_block, size_t total_size,
			 size_t offset)
{
	LOG_INF("write 3/0/14=%.*s", data_len, (char *)data);
	return 0;
}

static void set_ro_string(const struct lwm2m_obj_path *path, const char *value, uint16_t len)
{
	lwm2m_set_res_buf(path, (void *)value, len, len, LWM2M_RES_DATA_FLAG_RO);
}

int device_obj_init(void)
{
	set_ro_string(&LWM2M_OBJ(3, 0, 0), MANUFACTURER, sizeof(MANUFACTURER));
	set_ro_string(&LWM2M_OBJ(3, 0, 1), MODEL_NUMBER, sizeof(MODEL_NUMBER));
	set_ro_string(&LWM2M_OBJ(3, 0, 2), SERIAL_NUMBER, sizeof(SERIAL_NUMBER));
	set_ro_string(&LWM2M_OBJ(3, 0, 3), FIRMWARE_VER, sizeof(FIRMWARE_VER));
	set_ro_string(&LWM2M_OBJ(3, 0, 17), CONFIG_BOARD, sizeof(CONFIG_BOARD));
	set_ro_string(&LWM2M_OBJ(3, 0, 18), HARDWARE_VER, sizeof(HARDWARE_VER));

	lwm2m_register_exec_callback(&LWM2M_OBJ(3, 0, 4), reboot_cb);
	lwm2m_register_exec_callback(&LWM2M_OBJ(3, 0, 5), factory_default_cb);

	lwm2m_create_res_inst(&LWM2M_OBJ(3, 0, 6, 0));
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 6, 0), &pwr_src, sizeof(pwr_src), sizeof(pwr_src), 0);
	lwm2m_create_res_inst(&LWM2M_OBJ(3, 0, 7, 0));
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 7, 0), &pwr_mv, sizeof(pwr_mv), sizeof(pwr_mv), 0);
	lwm2m_create_res_inst(&LWM2M_OBJ(3, 0, 8, 0));
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 8, 0), &pwr_ma, sizeof(pwr_ma), sizeof(pwr_ma), 0);

	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 9), &bat_level, sizeof(bat_level), sizeof(bat_level), 0);
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 10), &mem_free, sizeof(mem_free), sizeof(mem_free), 0);
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 20), &bat_status, sizeof(bat_status),
			  sizeof(bat_status), 0);
	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 21), &mem_total, sizeof(mem_total), sizeof(mem_total),
			  0);

	lwm2m_set_res_buf(&LWM2M_OBJ(3, 0, 14), utc_offset, sizeof(utc_offset),
			  strlen(utc_offset) + 1, 0);
	return lwm2m_register_post_write_callback(&LWM2M_OBJ(3, 0, 14), utc_offset_cb);
}
