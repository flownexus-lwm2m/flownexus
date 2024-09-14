/*
 * Copyright (c) 2022 Nordic Semiconductor
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_MODULE_NAME app_temp
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(LOG_MODULE_NAME);

#include "modules.h"

#include <zephyr/drivers/hwinfo.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/net/lwm2m.h>
#include <zephyr/kernel.h>
#include <zephyr/random/random.h>
#include <stdint.h>

static struct k_work_delayable temp_work;
#define PERIOD K_SECONDS(10)

static struct lwm2m_ctx *client_ctx;

static void temp_work_cb(struct k_work *work)
{
	double t, h;
	int ret;

	if (IS_ENABLED(CONFIG_SHT4X)) {
		const struct device *dev = DEVICE_DT_GET_ANY(sensirion_sht4x);
		struct sensor_value val;

		if (!dev) {
			LOG_ERR("device not ready.");
			goto out;
		}
		if (sensor_sample_fetch(dev)) {
			LOG_ERR("temperature data update failed");
			goto out;
		}

		sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, &val);
		t = sensor_value_to_double(&val);
		sensor_channel_get(dev, SENSOR_CHAN_HUMIDITY, &val);
		h = sensor_value_to_double(&val);
		LOG_DBG("Temperature: %.2f, Humidity: %.2f", t, h);

	} else {
		/* Generate dummy temperature data */
		t = 20.0 + (double)sys_rand32_get() / UINT32_MAX * 5.0;
		h = 50.0 + (double)sys_rand32_get() / UINT32_MAX * 10.0;
	}

	lwm2m_set_f64(&LWM2M_OBJ(3303, 0, 5700), t);
	lwm2m_set_f64(&LWM2M_OBJ(3304, 0, 5700), h);

	ret = lwm2m_send_cb(client_ctx, &LWM2M_OBJ(3303, 0, 5700), 1, NULL);
	if (ret) {
		LOG_ERR("lwm2m_send_cb, error: %d", ret);
	}
	ret = lwm2m_send_cb(client_ctx, &LWM2M_OBJ(3304, 0, 5700), 1, NULL);
	if (ret) {
		LOG_ERR("lwm2m_send_cb, error: %d", ret);
	}

	/* As an alternative, you can send the values together. In that case
	 * flownexus assigns them to an event. The name of the event is the
	 * first object (3303 in this case).
	 *
	 * const struct lwm2m_obj_path path[2] = {
	 * 	LWM2M_OBJ(3303, 0, 5700),
	 * 	LWM2M_OBJ(3304, 0, 5700),
	 * };
	 * ret = lwm2m_send_cb(client_ctx, path, 2, NULL);
	 * if (ret) {
	 * 	LOG_ERR("lwm2m_send_cb, error: %d", ret);
	 * }
	 */

out:
	k_work_schedule(&temp_work, PERIOD);
}

void init_temp_sensor(struct lwm2m_ctx *client)
{
	client_ctx = client;

	if ((lwm2m_create_object_inst(&LWM2M_OBJ(3303, 0)) == 0) &&
	    (lwm2m_create_object_inst(&LWM2M_OBJ(3304, 0)) == 0)) {
		k_work_init_delayable(&temp_work, temp_work_cb);
		k_work_schedule(&temp_work, K_NO_WAIT);
	} else {
		LOG_ERR("Failed to create temperature object instance");
	}
}
