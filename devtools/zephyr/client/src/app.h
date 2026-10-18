/*
 * Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef FLOWNEXUS_APP_H_
#define FLOWNEXUS_APP_H_

#include <stdint.h>

int device_obj_init(void);
int sensors_obj_init(void);
int fota_obj_init(void);
int fota_set_state(uint8_t state);
int fota_set_result(uint8_t result);
int app_lwm2m_start(const char *endpoint);

#endif /* FLOWNEXUS_APP_H_ */
