/*
 * Copyright (c) 2024 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_MODULE_NAME app_time_series_obj
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(LOG_MODULE_NAME);

#include "modules.h"
#include <lwm2m_object.h>
#include <lwm2m_engine.h>
#include <zephyr/net/lwm2m.h>

#define N_SAMPLES	40
#define PERIOD		K_SECONDS(1)

#define TIME_SERIES_VERSION_MAJOR	1
#define TIME_SERIES_VERSION_MINOR	0
#define LWM2M_TIME_SERIES_ID		10300
#define LWM2M_TIME_SERIES_RAW_ID	0
#define TIME_SERIES_MAX_ID		1
/*
 * Calculate resource instances as follows:
 * start with EVENT_LOG_MAX_ID
 * subtract EXEC resources (0)
 */
#define RESOURCE_INSTANCE_COUNT (TIME_SERIES_MAX_ID - 0)

static struct k_work_delayable time_series_work;

static struct lwm2m_ctx *client_ctx;

/* resource state variables */
static uint8_t time_series_raw;
/* Allocate data cache storage */
static struct lwm2m_time_series_elem time_series_cache[N_SAMPLES];

static struct lwm2m_engine_obj lwm2m_time_series_obj;
static struct lwm2m_engine_obj_field fields[] = {
	OBJ_FIELD_DATA(LWM2M_TIME_SERIES_RAW_ID, R, U8),
};

static struct lwm2m_engine_obj_inst inst;
static struct lwm2m_engine_res res[TIME_SERIES_MAX_ID];
static struct lwm2m_engine_res_inst res_inst[RESOURCE_INSTANCE_COUNT];


void time_series_send_cb(enum lwm2m_send_status status)
{
	if (status == 0) {
		LOG_INF("Time series data sent successfully");
	} else {
		LOG_ERR("Time series data send failed");
	}

	/* Once the previous message is out, add new data */
	k_work_schedule(&time_series_work, PERIOD);
}

static void time_series_work_cb(struct k_work *work)
{
	int ret;
	static int sample;

	/* Assign a test payload that counts from 1 - N_SAMPLES */
	lwm2m_set_u8(&LWM2M_OBJ(LWM2M_TIME_SERIES_ID, 0,
				LWM2M_TIME_SERIES_RAW_ID), sample);
	if (sample < N_SAMPLES) {
		sample++;
		k_work_schedule(&time_series_work, PERIOD);
		LOG_INF("Sample: %d/%d", sample, N_SAMPLES);
		return;
	}

	LOG_INF("Sending time series data");
	ret = lwm2m_send_cb(client_ctx, &LWM2M_OBJ(LWM2M_TIME_SERIES_ID, 0,
						   LWM2M_TIME_SERIES_RAW_ID), 1,
			    time_series_send_cb);
	if (ret) {
		LOG_ERR("lwm2m_send_cb, error: %d", ret);
	}
	sample = 0;
}

static struct lwm2m_engine_obj_inst *lwm2m_time_series_obj_create(uint16_t obj_inst_id)
{
	int i = 0, j = 0;

	init_res_instance(res_inst, ARRAY_SIZE(res_inst));

	/* initialize instance resource data */
	INIT_OBJ_RES_DATA(LWM2M_TIME_SERIES_RAW_ID, res, i, res_inst, j,
			  &time_series_raw, sizeof(time_series_raw));

	inst.resources = res;
	inst.resource_count = i;

	LOG_INF("Created LwM2M Time Series instance: %d", obj_inst_id);
	return &inst;
}

void init_time_series_obj(struct lwm2m_ctx *client)
{
	client_ctx = client;
	struct lwm2m_engine_obj_inst *obj_inst = NULL;
	int ret = 0;

	/* initialize the Event Log field data */
	lwm2m_time_series_obj.obj_id = LWM2M_TIME_SERIES_ID;
	lwm2m_time_series_obj.version_major = TIME_SERIES_VERSION_MAJOR;
	lwm2m_time_series_obj.version_minor = TIME_SERIES_VERSION_MINOR;
	lwm2m_time_series_obj.is_core = false;
	lwm2m_time_series_obj.fields = fields;
	lwm2m_time_series_obj.field_count = ARRAY_SIZE(fields);
	lwm2m_time_series_obj.max_instance_count = 1U;
	lwm2m_time_series_obj.create_cb = lwm2m_time_series_obj_create;
	lwm2m_register_obj(&lwm2m_time_series_obj);

	/* auto create the first instance */
	ret = lwm2m_create_obj_inst(LWM2M_TIME_SERIES_ID, 0, &obj_inst);
	if (ret < 0) {
		LOG_ERR("Create LWM2M Pump Mon instance 0 error: %d", ret);
	}

	ret = lwm2m_enable_cache(&LWM2M_OBJ(LWM2M_TIME_SERIES_ID, 0, LWM2M_TIME_SERIES_RAW_ID),
				 time_series_cache, ARRAY_SIZE(time_series_cache));
	if (ret < 0) {
		LOG_ERR("Failed to enable cache for LWM2M Pump Mon instance 0: %d", ret);
	}

	k_work_init_delayable(&time_series_work, time_series_work_cb);
	k_work_schedule(&time_series_work, PERIOD);
}
