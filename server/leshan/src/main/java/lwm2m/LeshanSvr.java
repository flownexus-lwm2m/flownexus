/* Copyright (c) 2024-2026 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Parts of this code are based on the Leshan project
 * (https://www.eclipse.org/leshan/) licensed under the BSD 3-Clause License.
 */

package lwm2m;

import java.net.InetSocketAddress;

import org.eclipse.californium.core.config.CoapConfig;
import org.eclipse.jetty.ee10.servlet.ServletContextHandler;
import org.eclipse.jetty.ee10.servlet.ServletHolder;
import org.eclipse.jetty.server.Server;
import org.eclipse.leshan.core.node.LwM2mNode;
import org.eclipse.leshan.server.LeshanServer;
import org.eclipse.leshan.server.LeshanServerBuilder;
import org.eclipse.leshan.transport.californium.server.endpoint.CaliforniumServerEndpointsProvider;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;

import lwm2m.json.JacksonLwM2mNodeSerializer;
import lwm2m.servlet.CommandServlet;
import lwm2m.servlet.HealthServlet;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * LwM2M gateway: the Leshan server, the command API for Django on port 8080,
 * and the forwarder of device events to the Django ingest API.
 */
public class LeshanSvr {
    private static final Logger log = LoggerFactory.getLogger(LeshanSvr.class);
    private static final int HTTP_PORT = 8080;
    // Raise the CoAP block-wise reassembly limit from the Californium default
    // (8 KB) to 20 KB to support larger LwM2M Send payloads.
    private static final int MAX_RESOURCE_BODY_SIZE = 20480;

    public static void main(String[] args) {
        String ingestUri = System.getenv().getOrDefault("DATA_SENDER_URI", "http://0.0.0.0:8000");
        ObjectMapper mapper = createMapper();
        IngestClient ingest = new IngestClient(ingestUri, mapper);
        LeshanServer lwm2m = createLeshanServer(new IngestForwarder(ingest, mapper));
        Server web = createWebServer(lwm2m, mapper);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                web.stop();
            } catch (Exception e) {
                log.warn("Stopping web server failed", e);
            }
            lwm2m.destroy();
            ingest.stop();
        }));

        try {
            lwm2m.start();
            web.start();
            log.info("LwM2M server started, command API at {}, ingest at {}", web.getURI(), ingestUri);
        } catch (Exception e) {
            log.error("Unable to start the gateway", e);
            System.exit(1);
        }
    }

    static ObjectMapper createMapper() {
        SimpleModule module = new SimpleModule();
        module.addSerializer(LwM2mNode.class, new JacksonLwM2mNodeSerializer());
        return new ObjectMapper().registerModule(module);
    }

    private static LeshanServer createLeshanServer(IngestForwarder forwarder) {
        CaliforniumServerEndpointsProvider endpoints = new CaliforniumServerEndpointsProvider.Builder()
                .setConfiguration(cfg -> cfg.set(CoapConfig.MAX_RESOURCE_BODY_SIZE, MAX_RESOURCE_BODY_SIZE))
                .build();
        LeshanServerBuilder builder = new LeshanServerBuilder();
        builder.setEndpointsProviders(endpoints);
        LeshanServer server = builder.build();
        server.getRegistrationService().addListener(forwarder);
        server.getSendService().addListener(forwarder);
        return server;
    }

    private static Server createWebServer(LeshanServer lwm2m, ObjectMapper mapper) {
        Server server = new Server(new InetSocketAddress(HTTP_PORT));
        ServletContextHandler root = new ServletContextHandler("/");
        root.addServlet(new ServletHolder(new HealthServlet()), "/health");
        root.addServlet(new ServletHolder(new CommandServlet(lwm2m, mapper)), "/api/clients/*");
        server.setHandler(root);
        return server;
    }
}
