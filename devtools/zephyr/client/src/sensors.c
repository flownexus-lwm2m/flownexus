/*
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/lwm2m.h>

#include "app.h"

LOG_MODULE_REGISTER(app_sensors, LOG_LEVEL_INF);

#define SENSOR_VALUE_RID 5700
#define MIN_RANGE_RID 5603
#define MAX_RANGE_RID 5604
#define SENSOR_UNITS_RID 5701

struct sensor_obj {
	uint16_t obj_id;
	const char *units;
	double initial;
	double min_range;
	double max_range;
};

static struct sensor_obj sensors[] = {
	{IPSO_OBJECT_TEMP_SENSOR_ID, "Celsius", 20.0, -40.0, 125.0},
	{IPSO_OBJECT_HUMIDITY_SENSOR_ID, "%RH", 50.0, 0.0, 100.0},
};

int sensors_obj_init(void)
{
	ARRAY_FOR_EACH_PTR(sensors, s) {
		int ret = lwm2m_create_object_inst(&LWM2M_OBJ(s->obj_id, 0));

		if (ret < 0) {
			LOG_ERR("Cannot create object %u (%d)", s->obj_id, ret);
			return ret;
		}

		lwm2m_set_res_buf(&LWM2M_OBJ(s->obj_id, 0, SENSOR_UNITS_RID), (void *)s->units,
				  strlen(s->units) + 1, strlen(s->units) + 1,
				  LWM2M_RES_DATA_FLAG_RO);
		lwm2m_set_f64(&LWM2M_OBJ(s->obj_id, 0, MIN_RANGE_RID), s->min_range);
		lwm2m_set_f64(&LWM2M_OBJ(s->obj_id, 0, MAX_RANGE_RID), s->max_range);
		lwm2m_set_f64(&LWM2M_OBJ(s->obj_id, 0, SENSOR_VALUE_RID), s->initial);
	}

	return 0;
}
