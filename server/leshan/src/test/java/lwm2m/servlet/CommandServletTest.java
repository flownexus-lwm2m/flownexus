/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m.servlet;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Map;

import org.eclipse.leshan.core.node.LwM2mSingleResource;
import org.eclipse.leshan.core.request.ContentFormat;
import org.eclipse.leshan.core.response.ExecuteResponse;
import org.eclipse.leshan.core.response.ReadResponse;
import org.eclipse.leshan.core.response.WriteResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class CommandServletTest {
    @Test
    void deviceSuccessIs200WithCoapCode() {
        CommandServlet.Result result = CommandServlet.result(WriteResponse.success(), 5);

        assertEquals(200, result.status());
        assertEquals(Map.of("status", "CHANGED", "code", "2.04"), result.body());
    }

    @Test
    void readSuccessContainsContent() {
        LwM2mSingleResource content = LwM2mSingleResource.newStringResource(0, "Zephyr");
        CommandServlet.Result result = CommandServlet.result(ReadResponse.success(content), 5);

        assertEquals(200, result.status());
        assertEquals("2.05", result.body().get("code"));
        assertEquals(content, result.body().get("content"));
    }

    @Test
    void deviceErrorIs502WithCoapCodeAndMessage() {
        assertEquals(Map.of("status", "METHOD_NOT_ALLOWED", "code", "4.05"),
                CommandServlet.result(WriteResponse.methodNotAllowed(), 5).body());

        CommandServlet.Result result = CommandServlet.result(ExecuteResponse.internalServerError("boom"), 5);
        assertEquals(502, result.status());
        assertEquals(Map.of("status", "INTERNAL_SERVER_ERROR", "code", "5.00", "error", "boom"), result.body());
    }

    @Test
    void noResponseIs504() {
        CommandServlet.Result result = CommandServlet.result(null, 2);

        assertEquals(504, result.status());
        assertEquals(Map.of("error", "no device response within 2 s"), result.body());
    }

    @Test
    void parsesFormatAndTimeout() {
        assertNull(CommandServlet.parseFormat(null));
        assertEquals(ContentFormat.CBOR, CommandServlet.parseFormat("cbor"));
        assertEquals(5, CommandServlet.parseTimeout(null));
        assertEquals(30, CommandServlet.parseTimeout("30"));
        assertThrows(IllegalArgumentException.class, () -> CommandServlet.parseFormat("XML"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"0", "-1", "soon", ""})
    void rejectsInvalidTimeouts(String timeout) {
        assertThrows(IllegalArgumentException.class, () -> CommandServlet.parseTimeout(timeout));
    }
}
