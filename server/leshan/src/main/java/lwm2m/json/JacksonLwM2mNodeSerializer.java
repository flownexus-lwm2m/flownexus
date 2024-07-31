/*******************************************************************************
 * Copyright (c) 2013-2015 Sierra Wireless and others.
 *
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v2.0
 * and Eclipse Distribution License v1.0 which accompany this distribution.
 *
 * The Eclipse Public License is available at
 *    http://www.eclipse.org/legal/epl-v20.html
 * and the Eclipse Distribution License is available at
 *    http://www.eclipse.org/org/documents/edl-v10.html.
 *
 * Contributors:
 *     Sierra Wireless - initial API and implementation
 *     Orange - keep one JSON dependency
 *
 * Copyright (c) 2024 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 *******************************************************************************/
package lwm2m.json;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Map.Entry;

import org.eclipse.leshan.core.link.DefaultLinkSerializer;
import org.eclipse.leshan.core.link.Link;
import org.eclipse.leshan.core.link.LinkSerializer;
import org.eclipse.leshan.core.model.ResourceModel.Type;
import org.eclipse.leshan.core.node.LwM2mChildNode;
import org.eclipse.leshan.core.node.LwM2mNode;
import org.eclipse.leshan.core.node.LwM2mObject;
import org.eclipse.leshan.core.node.LwM2mObjectInstance;
import org.eclipse.leshan.core.node.LwM2mResource;
import org.eclipse.leshan.core.node.LwM2mResourceInstance;
import org.eclipse.leshan.core.node.LwM2mRoot;
import org.eclipse.leshan.core.util.Hex;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.ser.std.StdSerializer;

public class JacksonLwM2mNodeSerializer extends StdSerializer<LwM2mNode> {

    private static final long serialVersionUID = 1L;

    private final LinkSerializer linkSerializer = new DefaultLinkSerializer();

    protected JacksonLwM2mNodeSerializer(Class<LwM2mNode> t) {
        super(t);
    }

    public JacksonLwM2mNodeSerializer() {
        this(null);
    }

    @Override
    public void serialize(LwM2mNode node, JsonGenerator gen, SerializerProvider provider) throws IOException {
        Map<String, Object> element = new HashMap<>();

        if (!(node instanceof LwM2mChildNode)) {
            // Handle root node
            if (node instanceof LwM2mRoot) {
                element.put("kind", "root");
                element.put("objects", ((LwM2mRoot) node).getObjects().values());
            } else {
                throw new UnsupportedOperationException("Unsupported node : " + node.getClass().getSimpleName());
            }
        } else {
            // Handle child node
            LwM2mChildNode childNode = (LwM2mChildNode) node;
            element.put("id", childNode.getId());
            if (childNode instanceof LwM2mObject) {
                element.put("kind", "obj");
                element.put("instances", ((LwM2mObject) childNode).getInstances().values());
            } else if (childNode instanceof LwM2mObjectInstance) {
                element.put("kind", "instance");
                element.put("resources", ((LwM2mObjectInstance) childNode).getResources().values());
            } else if (childNode instanceof LwM2mResource) {
                LwM2mResource rsc = (LwM2mResource) childNode;
                if (rsc.isMultiInstances()) {
                    Map<String, Object> values = new HashMap<>();
                    for (Entry<Integer, LwM2mResourceInstance> entry : rsc.getInstances().entrySet()) {
                        values.put(entry.getKey().toString(), convertValue(rsc.getType(), entry.getValue().getValue()));
                    }
                    element.put("kind", "multiResource");
                    element.put("values", values);
                    element.put("type", rsc.getType());
                } else {
                    element.put("kind", "singleResource");
                    element.put("type", rsc.getType());
                    element.put("value", convertValue(rsc.getType(), rsc.getValue()));
                }
            } else if (childNode instanceof LwM2mResourceInstance) {
                element.put("kind", "resourceInstance");
                LwM2mResourceInstance rsc = (LwM2mResourceInstance) childNode;
                element.put("type", rsc.getType());
                element.put("value", convertValue(rsc.getType(), rsc.getValue()));
            } else {
                throw new UnsupportedOperationException("Unsupported node : " + node.getClass().getSimpleName());
            }
        }
        gen.writeObject(element);
    }

    private Object convertValue(Type type, Object value) {
        switch (type) {
        case OPAQUE:
            return new String(Hex.encodeHex((byte[]) value));
        case INTEGER:
        case UNSIGNED_INTEGER:
            // we use String for INTEGER and UNSIGNED INTEGER because
            // Javascript number does not support safely number larger than Number.MAX_SAFE_INTEGER (2^53 - 1)
            // without usage of BigInt...
            return value.toString();
        case FLOAT:
            // We use String to be consistent with INTEGER but to be sure to not get any restriction from javascript
            // world.
            return value.toString();
        case CORELINK:
            return linkSerializer.serializeCoreLinkFormat((Link[]) value);
        default:
            return value;
        }
    }
}
