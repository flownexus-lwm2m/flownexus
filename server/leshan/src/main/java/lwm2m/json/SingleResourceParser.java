/* Copyright (c) 2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m.json;

import java.util.Date;

import org.eclipse.leshan.core.model.ResourceModel.Type;
import org.eclipse.leshan.core.node.LwM2mSingleResource;
import org.eclipse.leshan.core.util.Hex;
import org.eclipse.leshan.core.util.datatype.ULong;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Parses the body of a write command, {"id", "kind": "singleResource",
 * "type", "value"}, into a Leshan resource. TIME values are epoch
 * milliseconds, OPAQUE values are hex strings.
 */
public final class SingleResourceParser {
    private SingleResourceParser() {
    }

    public static LwM2mSingleResource parse(JsonNode body) {
        if (body == null || !body.isObject()) {
            throw new IllegalArgumentException("expected a JSON object");
        }
        if (body.has("kind") && !"singleResource".equals(body.get("kind").asText())) {
            throw new IllegalArgumentException("only a single resource can be written");
        }
        JsonNode id = body.get("id");
        JsonNode type = body.get("type");
        JsonNode value = body.get("value");
        if (id == null || !id.canConvertToInt() || type == null || value == null) {
            throw new IllegalArgumentException("expected fields id, type and value");
        }
        Type resourceType;
        try {
            resourceType = Type.valueOf(type.asText().toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("unknown type: " + type.asText());
        }
        return LwM2mSingleResource.newResource(id.asInt(), value(value, resourceType), resourceType);
    }

    private static Object value(JsonNode value, Type type) {
        return switch (type) {
            case STRING -> {
                if (!value.isTextual()) {
                    throw new IllegalArgumentException("STRING value must be a JSON string");
                }
                yield value.asText();
            }
            case INTEGER -> value.isIntegralNumber() ? value.asLong() : Long.parseLong(value.asText());
            case UNSIGNED_INTEGER -> ULong.valueOf(value.asText());
            case FLOAT -> value.isNumber() ? value.asDouble() : Double.parseDouble(value.asText());
            case BOOLEAN -> {
                if (value.isBoolean()) {
                    yield value.asBoolean();
                }
                if (value.isIntegralNumber() && (value.asInt() == 0 || value.asInt() == 1)) {
                    yield value.asInt() == 1;
                }
                throw new IllegalArgumentException("BOOLEAN value must be true, false, 0 or 1");
            }
            case OPAQUE -> Hex.decodeHex(value.asText().toCharArray());
            case TIME -> {
                if (!value.isIntegralNumber()) {
                    throw new IllegalArgumentException("TIME value must be epoch milliseconds");
                }
                yield new Date(value.asLong());
            }
            default -> throw new IllegalArgumentException("type " + type + " cannot be written");
        };
    }
}
