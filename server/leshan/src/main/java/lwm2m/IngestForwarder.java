/* Copyright (c) 2024 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package lwm2m;

import java.time.Instant;
import java.util.Collection;
import java.util.Map;

import org.eclipse.leshan.core.node.LwM2mNode;
import org.eclipse.leshan.core.node.LwM2mPath;
import org.eclipse.leshan.core.node.TimestampedLwM2mNodes;
import org.eclipse.leshan.core.observation.Observation;
import org.eclipse.leshan.core.request.SendRequest;
import org.eclipse.leshan.server.registration.Registration;
import org.eclipse.leshan.server.registration.RegistrationListener;
import org.eclipse.leshan.server.registration.RegistrationUpdate;
import org.eclipse.leshan.server.send.SendListener;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Forwards registration events and LwM2M Send data to Django. */
public class IngestForwarder implements RegistrationListener, SendListener {
    private static final Logger log = LoggerFactory.getLogger(IngestForwarder.class);

    private final IngestClient ingest;
    private final ObjectMapper mapper;

    public IngestForwarder(IngestClient ingest, ObjectMapper mapper) {
        this.ingest = ingest;
        this.mapper = mapper;
    }

    private void registrationEvent(String endpoint, String event, Instant time) {
        ObjectNode node = mapper.createObjectNode();
        node.put("ep", endpoint);
        node.put("event", event);
        node.put("time", time.toString());
        ingest.post(IngestClient.REGISTRATION, node);
    }

    @Override
    public void registered(Registration registration, Registration previousReg,
                           Collection<Observation> previousObservations) {
        log.trace("Registered: {}", registration.getEndpoint());
        registrationEvent(registration.getEndpoint(), "registered",
                registration.getRegistrationDate().toInstant());
    }

    @Override
    public void updated(RegistrationUpdate update, Registration updatedReg, Registration previousReg) {
        log.trace("Updated: {}", updatedReg.getEndpoint());
        registrationEvent(updatedReg.getEndpoint(), "updated", updatedReg.getLastUpdate().toInstant());
    }

    @Override
    public void unregistered(Registration registration, Collection<Observation> observations,
                             boolean expired, Registration newReg) {
        log.trace("Unregistered: {} (expired: {})", registration.getEndpoint(), expired);
        registrationEvent(registration.getEndpoint(), "unregistered", Instant.now());
    }

    @Override
    public void dataReceived(Registration registration, TimestampedLwM2mNodes data, SendRequest request) {
        log.trace("Send from: {}", registration.getEndpoint());

        ArrayNode values = mapper.createArrayNode();
        for (Instant ts : data.getTimestamps()) {
            ObjectNode nodes = mapper.createObjectNode();
            Map<LwM2mPath, LwM2mNode> nodesAtTimestamp = data.getNodesAt(ts);
            if (nodesAtTimestamp != null) {
                for (Map.Entry<LwM2mPath, LwM2mNode> e : nodesAtTimestamp.entrySet()) {
                    nodes.set(e.getKey().toString(), mapper.valueToTree(e.getValue()));
                }
            }
            ObjectNode entry = mapper.createObjectNode();
            entry.set("nodes", nodes);
            values.addObject().set(ts == null ? "null" : ts.toString(), entry);
        }

        ObjectNode root = mapper.createObjectNode();
        root.put("ep", registration.getEndpoint());
        root.set("val", values);
        ingest.post(IngestClient.TIMESTAMPED, root);
    }

    @Override
    public void onError(Registration registration, String errorMessage, Exception error) {
        log.error("Unable to handle Send from {}: {}", registration.getEndpoint(), errorMessage, error);
    }
}
