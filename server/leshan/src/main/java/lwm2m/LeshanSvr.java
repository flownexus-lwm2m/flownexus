/* Copyright (c) 2024 Jonas Remmert
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Parts of this code are based on the Leshan project
 * (https://www.eclipse.org/leshan/) licensed under the BSD 3-Clause License.
 */

package lwm2m;
import java.util.ArrayList;
import java.util.List;
import java.net.InetAddress;
import java.net.InetSocketAddress;

import org.eclipse.leshan.server.LeshanServer;
import org.eclipse.leshan.server.LeshanServerBuilder;
import org.eclipse.leshan.core.request.DiscoverRequest;
import org.eclipse.leshan.core.response.DiscoverResponse;
import org.eclipse.leshan.core.observation.Observation;
import org.eclipse.leshan.core.observation.CompositeObservation;
import org.eclipse.leshan.core.observation.SingleObservation;
import org.eclipse.leshan.core.request.ObserveRequest;
import org.eclipse.leshan.core.request.ObserveCompositeRequest;
import org.eclipse.leshan.core.response.ObserveCompositeResponse;
import org.eclipse.leshan.core.response.ObserveResponse;
import org.eclipse.leshan.core.request.ContentFormat;
import org.eclipse.leshan.server.send.SendListener;
import org.eclipse.leshan.core.request.SendRequest;
import org.eclipse.leshan.core.request.ReadRequest;
import org.eclipse.leshan.core.response.ReadResponse;
import org.eclipse.leshan.core.node.TimestampedLwM2mNodes;
import org.eclipse.leshan.core.LwM2m.Version;
import org.eclipse.leshan.core.link.Link;
import org.eclipse.leshan.core.link.lwm2m.LwM2mLink;
import org.eclipse.leshan.core.node.LwM2mNode;
import org.eclipse.leshan.core.node.LwM2mPath;
import org.eclipse.leshan.server.registration.Registration;
import org.eclipse.leshan.server.registration.RegistrationListener;
import org.eclipse.leshan.server.registration.RegistrationUpdate;
import org.eclipse.leshan.server.observation.ObservationListener;
import org.eclipse.leshan.server.californium.endpoint.CaliforniumServerEndpointsProvider;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.DefaultServlet;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;
import org.eclipse.jetty.servlets.EventSource;
import org.eclipse.jetty.servlets.EventSourceServlet;

import lwm2m.json.JacksonLinkSerializer;
import lwm2m.json.JacksonLwM2mNodeSerializer;
import lwm2m.json.JacksonRegistrationSerializer;
import lwm2m.json.JacksonVersionSerializer;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.databind.SerializationFeature;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.Collection;
import java.nio.ByteBuffer;

import lwm2m.DataSenderRest;
import lwm2m.servlet.ClientServlet;
import lwm2m.servlet.EventServlet;
import lwm2m.servlet.ObjectSpecServlet;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;


public class LeshanSvr{
    private final ExecutorService onboardingExecutor = Executors.newCachedThreadPool();
    private static DataSenderRest dataSenderRest = new DataSenderRest();
    private LeshanServer server;
    private ObjectMapper mapper;
    private SimpleModule module;
    private static final Logger log = LoggerFactory.getLogger(LeshanSvr.class);

    public LeshanSvr() {
        LeshanServerBuilder builder = new LeshanServerBuilder();
        builder.setEndpointsProviders(new CaliforniumServerEndpointsProvider());
        server = builder.build();
        mapper = new ObjectMapper();
        module = new SimpleModule();

        module.addSerializer(Link.class, new JacksonLinkSerializer());
        module.addSerializer(LwM2mNode.class, new JacksonLwM2mNodeSerializer());
        module.addSerializer(Version.class, new JacksonVersionSerializer());
        mapper.registerModule(module);

        server.getRegistrationService().addListener(new MyRegistrationListener(this));
        server.getObservationService().addListener(new MyObservationListener(this));
        server.getSendService().addListener(new MySendListener(this));
    }

    public static void main(String[] args) {
        final LeshanSvr lwm2mServer = new LeshanSvr();
        Server webServer = createJettyServer(lwm2mServer.server);

        // Add a shutdown hook to cleanly shutdown the resources
        Runtime.getRuntime().addShutdownHook(new Thread(() -> lwm2mServer.stop()));

        try {
            lwm2mServer.start();
            webServer.start();
            log.info("Web server started at {}.", webServer.getURI());

        } catch (Exception e) {

            log.error("Unable to create and start server ...", e);
            System.exit(1);
        }
    }

    public void start() {
        server.start();
        log.info("LeshanServer started");
    }

    public void stop() {
        if (server != null) {
            server.stop();
        }

        this.onboardingExecutor.shutdown();
        try {
            if (!this.onboardingExecutor.awaitTermination(60, TimeUnit.SECONDS)) {
                this.onboardingExecutor.shutdownNow();

                if (!this.onboardingExecutor.awaitTermination(60, TimeUnit.SECONDS)) {
                    log.error("Pool did not terminate");
                }
            }
        } catch (InterruptedException ie) {
            this.onboardingExecutor.shutdownNow();
            Thread.currentThread().interrupt(); // Preserve interrupt status
        }
    }

    private static Server createJettyServer(LeshanServer lwServer) {
        // Now prepare Jetty
        InetSocketAddress jettyAddr = new InetSocketAddress(8080);
        Server server = new Server(jettyAddr);
        ServletContextHandler root = new ServletContextHandler(null, "/", true, false);
        server.setHandler(root);

        // Create REST API Servlets
        EventServlet eventServlet = new EventServlet(lwServer);
        ServletHolder eventServletHolder = new ServletHolder(eventServlet);
        root.addServlet(eventServletHolder, "/api/event/*");

        ClientServlet clientServlet = new ClientServlet(lwServer);
        ServletHolder clientServletHolder = new ServletHolder(clientServlet);
        root.addServlet(clientServletHolder, "/api/clients/*");

        ObjectSpecServlet objectSpecServlet = new ObjectSpecServlet(
                                                    lwServer.getModelProvider(),
                                                    lwServer.getRegistrationService()
                                                    );
        ServletHolder objectSpecServletHolder = new ServletHolder(objectSpecServlet);
        root.addServlet(objectSpecServletHolder, "/api/objectspecs/*");

        return server;
    }

    private void onboardingDevice(Registration registration) {
        log.trace("Onboarding " + registration.getEndpoint());
        onboardingExecutor.submit(() -> {
            LwM2mLink[] res;
            try {
                DiscoverResponse discoverResponse = server.send(registration,
                                                                new DiscoverRequest(3));
                if (discoverResponse.isSuccess()) {
                    res = discoverResponse.getObjectLinks();
                    if (res != null) {
                        log.trace("Resources:");
                        for (LwM2mLink link : res) {
                            log.trace(link.toString());
                        }
                    } else {
                        log.error("No resources found.");
                    }
                } else {
                    log.error("Failed to discover resources: " +
                                 discoverResponse.getErrorMessage());
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }

            try {
                ReadResponse readResp = server.send(registration, new ReadRequest(3));
                if (readResp.isSuccess()) {
                    /* Match the additional hierachiy of the observe response format */
                    mapper.enable(SerializationFeature.INDENT_OUTPUT);
                    ObjectNode node = mapper.createObjectNode();
                    node.put("ep", registration.getEndpoint());
                    ObjectNode valNode = mapper.createObjectNode();
                    valNode.set("/3", mapper.valueToTree(readResp.getContent()));
                    node.set("val", valNode);

                    dataSenderRest.sendData(ApiPath.COMPOSITE_RES, node);
                } else {
                    log.error("Failed to read resources: " +
                                 readResp.getErrorMessage());
                }
            } catch (InterruptedException e) {
                log.error("Failed to read resources: " + e.getMessage());
                e.printStackTrace();
            }

            /* Subscribe to single resource instances as an example */
            int[][] singleObjectLinks = {
                //{3303, 0, 5700},   /* Temperature Sensor */
                //{3304, 0, 5700},   /* Humidity Sensor */
                //{5, 0, 3},      /* Firmware Update State */
                //{5, 0, 5}      /* Firmware Update Result */
            };

            for (int[] link : singleObjectLinks) {
                try {
                    ObserveRequest req;
                    if (link.length != 3) {
                        throw new IllegalArgumentException("Invalid link format");
                    }
                    req = new ObserveRequest(link[0], link[1], link[2]);
                    server.send(registration, req);
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
            }

            /* Subscribe to composite object instances as an example
             * 10300: Custom Object Instance
             */
            int[][] compositeObjectLinks = {
                //{10300},
            };

            for (int[] link : compositeObjectLinks) {
                try {
                    List<LwM2mPath> paths = new ArrayList<>();
                    paths.add(new LwM2mPath(link[0]));

                    // Specify the content formats
                    ContentFormat requestContentFormat = ContentFormat.SENML_CBOR;
                    ContentFormat responseContentFormat = ContentFormat.SENML_CBOR;

                    // Create the ObserveCompositeRequest for the whole object instance
                    ObserveCompositeRequest observeCompositeRequest = new ObserveCompositeRequest(
                        requestContentFormat,
                        responseContentFormat,
                        paths
                    );

                    log.trace("Sending ObserveCompositeRequest: " + observeCompositeRequest);
                    server.send(registration, observeCompositeRequest);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        });
    }

    public class MyRegistrationListener implements RegistrationListener {
        private final LeshanSvr server;
        private static final Logger log = LoggerFactory.getLogger(MyRegistrationListener.class);

        public MyRegistrationListener(LeshanSvr server) {
            this.server = server;
        }

        @Override
        public void registered(Registration registration, Registration previousReg,
                               Collection<Observation> previousObsersations) {
            log.trace("new device registered: " + registration.getEndpoint());

            ObjectNode node = mapper.createObjectNode();
            node.put("ep", registration.getEndpoint());
            node.put("obj_id", 10240);
            ObjectNode valNode = mapper.createObjectNode();
            valNode.put("kind", "singleResource");
            valNode.put("id", 0);
            valNode.put("type", "TIME");
            valNode.put("value", registration.getRegistrationDate().getTime());
            node.set("val", valNode);

            dataSenderRest.sendData(ApiPath.SINGLE_RES, node);

            /* Onboarding: read and subscribe to device resources initially.
             * TODO: Remove this onboarding, it should be triggered by Django
             */
            server.onboardingDevice(registration);
        }

        @Override
        public void updated(RegistrationUpdate update, Registration updatedReg,
                            Registration previousReg) {
            log.trace("Device updated: " + updatedReg.getEndpoint());

            ObjectNode node = mapper.createObjectNode();
            node.put("ep", updatedReg.getEndpoint());
            node.put("obj_id", 10240);
            ObjectNode valNode = mapper.createObjectNode();
            valNode.put("kind", "singleResource");
            valNode.put("id", 2);
            valNode.put("type", "TIME");
            valNode.put("value", updatedReg.getRegistrationDate().getTime());
            node.set("val", valNode);

            dataSenderRest.sendData(ApiPath.SINGLE_RES, node);
        }

        @Override
        public void unregistered(Registration registration,
                                 Collection<Observation> observations,
                                 boolean expired,
                                 Registration newReg) {
            log.trace("Device left: " + registration.getEndpoint());

            ObjectNode node = mapper.createObjectNode();
            node.put("ep", registration.getEndpoint());
            node.put("obj_id", 10240);
            ObjectNode valNode = mapper.createObjectNode();
            valNode.put("kind", "singleResource");
            valNode.put("id", 1);
            valNode.put("type", "TIME");
            valNode.put("value", registration.getRegistrationDate().getTime());
            node.set("val", valNode);

            dataSenderRest.sendData(ApiPath.SINGLE_RES, node);
        }
    }


    public class MyObservationListener implements ObservationListener {
        private final LeshanSvr server;
        private static final Logger log = LoggerFactory.getLogger(MyObservationListener.class);

        public MyObservationListener(LeshanSvr server) {
            this.server = server;
        }

        @Override
        public void cancelled(Observation observation) {
        }

        @Override
        public void onResponse(SingleObservation observation,
                               Registration registration,
                               ObserveResponse response) {
            mapper.enable(SerializationFeature.INDENT_OUTPUT);
            log.trace("onResponse: " + response.getContent());

            if (registration != null) {
                ObjectNode node = mapper.createObjectNode();
                node.put("ep", registration.getEndpoint());
                node.put("obj_id", observation.getPath().getObjectId());
                node.set("val", mapper.valueToTree(response.getContent()));

                dataSenderRest.sendData(ApiPath.SINGLE_RES, node);
            }
        }

        @Override
        public void onResponse(CompositeObservation observation,
                               Registration registration,
                               ObserveCompositeResponse response) {
            log.trace("onResponse: " + response.getContent());

            mapper.enable(SerializationFeature.INDENT_OUTPUT);
            ObjectNode node = mapper.createObjectNode();
            node.put("ep", registration.getEndpoint());
            node.set("val", mapper.valueToTree(response.getContent()));

            dataSenderRest.sendData(ApiPath.COMPOSITE_RES, node);
        }


        @Override
        public void onError(Observation observation, Registration registration, Exception error) {
            log.error("onError: " + registration.getEndpoint());
            log.error("onError: " + error);
        }

        @Override
        public void newObservation(Observation observation, Registration registration) {
        }
    }

    public class MySendListener implements SendListener {
        private final LeshanSvr server;
        private static final Logger log = LoggerFactory.getLogger(MySendListener.class);

        public MySendListener(LeshanSvr server) {
            this.server = server;
        }

        @Override
        public void dataReceived(Registration registration,
                                 TimestampedLwM2mNodes data,
                                 SendRequest request) {
            log.trace("dataReceived from: " + registration.getEndpoint());

            mapper.enable(SerializationFeature.INDENT_OUTPUT);
            ObjectNode node = mapper.createObjectNode();
            node.put("ep", registration.getEndpoint());
            node.set("val", mapper.valueToTree(data));

            dataSenderRest.sendData(ApiPath.TIMESTAMPED_RES, node);
        }

        @Override
        public void onError(Registration registration,
                            String errorMessage,
                            Exception error) {
            log.error("Unable to handle Send Request from: " + registration.getEndpoint());
            log.error(errorMessage);
            log.error(error.toString());
        }
    }
}
