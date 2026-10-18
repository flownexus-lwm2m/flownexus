/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m.json;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Date;

import org.eclipse.leshan.core.model.ResourceModel.Type;
import org.eclipse.leshan.core.node.LwM2mSingleResource;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import com.fasterxml.jackson.databind.ObjectMapper;

class SingleResourceParserTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static LwM2mSingleResource parse(String json) throws Exception {
        return SingleResourceParser.parse(MAPPER.readTree(json));
    }

    private static LwM2mSingleResource resource(String type, String value) throws Exception {
        return parse("{\"id\": 14, \"kind\": \"singleResource\", \"type\": \"" + type + "\", \"value\": " + value + "}");
    }

    @Test
    void parsesTheTypesDjangoSends() throws Exception {
        assertEquals("+02:00", resource("STRING", "\"+02:00\"").getValue());
        assertEquals(42L, resource("INTEGER", "42").getValue());
        assertEquals(42L, resource("INTEGER", "\"42\"").getValue());
        assertEquals(21.5, resource("FLOAT", "21.5").getValue());
        assertEquals(true, resource("BOOLEAN", "1").getValue());
        assertEquals(false, resource("BOOLEAN", "false").getValue());
        assertEquals(new Date(1767225600000L), resource("TIME", "1767225600000").getValue());
        assertArrayEquals(new byte[] {0x0a, (byte) 0xff}, (byte[]) resource("OPAQUE", "\"0aff\"").getValue());

        LwM2mSingleResource string = resource("string", "\"x\"");
        assertEquals(14, string.getId());
        assertEquals(Type.STRING, string.getType());
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "[]",
        "{\"id\": 14, \"type\": \"STRING\"}",
        "{\"id\": 14, \"kind\": \"multiResource\", \"type\": \"STRING\", \"value\": \"x\"}",
        "{\"id\": 14, \"type\": \"NONE\", \"value\": \"x\"}",
        "{\"id\": 14, \"type\": \"NOPE\", \"value\": \"x\"}",
        "{\"id\": 14, \"type\": \"STRING\", \"value\": 5}",
        "{\"id\": 14, \"type\": \"BOOLEAN\", \"value\": 2}",
        "{\"id\": 14, \"type\": \"INTEGER\", \"value\": \"abc\"}",
        "{\"id\": 14, \"type\": \"TIME\", \"value\": \"now\"}",
    })
    void rejectsInvalidBodies(String json) {
        assertThrows(IllegalArgumentException.class, () -> parse(json));
    }
}
