/*
 * Copyright (c) 2022 Nordic Semiconductor
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef _MODULES_H
#define _MODULES_H

#include <zephyr/net/lwm2m.h>

int init_led_device(void);
void init_timer_object(void);
void init_temp_sensor(struct lwm2m_ctx *client);
void init_firmware_update(struct lwm2m_ctx *client);


#endif
