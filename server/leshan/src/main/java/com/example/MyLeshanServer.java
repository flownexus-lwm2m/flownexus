package com.example;
import java.util.ArrayList;
import java.util.List;

import org.eclipse.leshan.server.LeshanServer;
import org.eclipse.leshan.server.LeshanServerBuilder;
import org.eclipse.leshan.core.request.DiscoverRequest;
import org.eclipse.leshan.core.response.DiscoverResponse;
import org.eclipse.leshan.core.observation.Observation;
import org.eclipse.leshan.core.observation.CompositeObservation;
import org.eclipse.leshan.core.observation.SingleObservation;
import org.eclipse.leshan.core.request.ObserveRequest;
import org.eclipse.leshan.core.response.ObserveCompositeResponse;
import org.eclipse.leshan.core.response.ObserveResponse;
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

import com.example.json.JacksonLinkSerializer;
import com.example.json.JacksonLwM2mNodeSerializer;
import com.example.json.JacksonRegistrationSerializer;
import com.example.json.JacksonVersionSerializer;

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

import com.example.DataSenderRest;


public class MyLeshanServer {
    private final ExecutorService onboardingExecutor = Executors.newCachedThreadPool();
    private static DataSenderRest dataSenderRest = new DataSenderRest();
    private LeshanServer server;
    private ObjectMapper mapper;
    private SimpleModule module;

    public MyLeshanServer() {
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
    }

    public static void main(String[] args) {
        final MyLeshanServer myServer = new MyLeshanServer();

        // Add a shutdown hook to cleanly shutdown the resources
        Runtime.getRuntime().addShutdownHook(new Thread(() -> myServer.stop()));

        myServer.start();
    }

    public void start() {
        server.start();
        System.out.println("LeshanServer started");
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
                    System.err.println("Pool did not terminate");
                }
            }
        } catch (InterruptedException ie) {
            this.onboardingExecutor.shutdownNow();
            Thread.currentThread().interrupt(); // Preserve interrupt status
        }
    }

    private void onboardingDevice(Registration registration) {
        System.out.println("Onboarding " + registration.getEndpoint());
        onboardingExecutor.submit(() -> {
            LwM2mLink[] res;
            try {
                DiscoverResponse discoverResponse = server.send(registration,
                                                                new DiscoverRequest(3));
                if (discoverResponse.isSuccess()) {
                    res = discoverResponse.getObjectLinks();
                    if (res != null) {
                        System.out.println("Resources:");
                        for (LwM2mLink link : res) {
                            System.out.println(link);
                        }
                    } else {
                        System.out.println("No resources found.");
                    }
                } else {
                    System.err.println("Failed to discover resources: " +
                                             discoverResponse.getErrorMessage());
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }

            try {
                ReadResponse readResp = server.send(registration, new ReadRequest(3));
                if (readResp.isSuccess()) {
                    mapper.enable(SerializationFeature.INDENT_OUTPUT);
                    String jsonContent = null;
                    try {
                        jsonContent = mapper.writeValueAsString(readResp.getContent());
                    } catch (JsonProcessingException e) {
                        throw new RuntimeException(e);
                    }
                    System.out.println(jsonContent);
                    String data = new StringBuilder("{\"ep\":\"") //
                            .append(registration.getEndpoint()) //
                            .append("\",\"res\":\"3\"") //
                            .append("\",\"val\":") //
                            .append(jsonContent) //
                            .append("}") //
                            .toString();
                    dataSenderRest.sendData(data);
                } else {
                    System.err.println("Failed to read resources: " +
                                             readResp.getErrorMessage());
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }

            try {
                ReadResponse readResp = server.send(registration, new ReadRequest(3));
                if (readResp.isSuccess()) {
                    mapper.enable(SerializationFeature.INDENT_OUTPUT);
                    String jsonContent = null;
                    try {
                        jsonContent = mapper.writeValueAsString(readResp.getContent());
                    } catch (JsonProcessingException e) {
                        throw new RuntimeException(e);
                    }
                    System.out.println(jsonContent);
                    String data = new StringBuilder("{\"ep\":\"") //
                            .append(registration.getEndpoint()) //
                            .append("\",\"res\":\"3\"") //
                            .append(",\"val\":") //
                            .append(jsonContent) //
                            .append("}") //
                            .toString();
                    dataSenderRest.sendData(data);
                } else {
                    System.err.println("Failed to read resources: " +
                                             readResp.getErrorMessage());
                }
            } catch (InterruptedException e) {
                e.printStackTrace();
            }

            /* Subscribe to individual objects */
            int[][] objectLinks = {{3303, 0, 5700}, {3304, 0, 5701}, {3305, 0, 5702}};
            for (int[] link : objectLinks) {
                ObserveRequest observeRequest = new ObserveRequest(link[0], link[1], link[2]);
                try {
                    server.send(registration, observeRequest);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        });
    }

    public class MyRegistrationListener implements RegistrationListener {
        private final MyLeshanServer server;

        public MyRegistrationListener(MyLeshanServer server) {
            this.server = server;
        }

        @Override
        public void registered(Registration registration, Registration previousReg,
                                      Collection<Observation> previousObsersations) {
            System.out.println("new device registered: " + registration.getEndpoint());
            /* Onboarding: read and subscribe to device resources initially.*/
            server.onboardingDevice(registration);
        }

        @Override
        public void updated(RegistrationUpdate update, Registration updatedReg,
                                  Registration previousReg) {
            System.out.println("Device updated: " + updatedReg.getEndpoint());
        }

        @Override
        public void unregistered(Registration registration, Collection<Observation> observations,
                                         boolean expired,
                                         Registration newReg) {
            System.out.println("Device left: " + registration.getEndpoint());
        }
    }


    public class MyObservationListener implements ObservationListener {
        private final MyLeshanServer server;

        public MyObservationListener(MyLeshanServer server) {
            this.server = server;
        }

        @Override
        public void cancelled(Observation observation) {
        }

        @Override
        public void onResponse(SingleObservation observation, Registration registration,
                                      ObserveResponse response) {
            mapper.enable(SerializationFeature.INDENT_OUTPUT);
            //System.out.println("onResponse (single): " + response);
            String jsonContent = null;
            try {
                jsonContent = mapper.writeValueAsString(response.getContent());
            } catch (JsonProcessingException e) {
                throw new RuntimeException(e);
            }

            if (registration != null) {
                String data = new StringBuilder("{\"ep\":\"") //
                        .append(registration.getEndpoint()) //
                        .append("\",\"res\":\"") //
                        .append(observation.getPath()).append("\",\"val\":") //
                        .append(jsonContent) //
                        .append("}") //
                        .toString();

                dataSenderRest.sendData(data);
            }
        }

        @Override
        public void onResponse(CompositeObservation observation, Registration registration,
                                      ObserveCompositeResponse response) {
            String jsonContent = null;
            String jsonListOfPath = null;
            try {
                jsonContent = mapper.writeValueAsString(response.getContent());
                List<String> paths = new ArrayList<String>();
                for (LwM2mPath path : response.getObservation().getPaths()) {
                    paths.add(path.toString());
                }
                jsonListOfPath = mapper.writeValueAsString(paths);
            } catch (JsonProcessingException e) {
                throw new RuntimeException(e);
            }

            if (registration != null) {
                String data = new StringBuilder("{\"ep\":\"") //
                        .append(registration.getEndpoint()) //
                        .append("\",\"val\":") //
                        .append(jsonContent) //
                        .append(",\"paths\":") //
                        .append(jsonListOfPath) //
                        .append("}") //
                        .toString();

                dataSenderRest.sendData(data);
            }
        }


        @Override
        public void onError(Observation observation, Registration registration, Exception error) {
            System.out.println("onError: " + registration.getEndpoint());
            System.out.println("onError: " + error);
        }

        @Override
        public void newObservation(Observation observation, Registration registration) {
        }
    }

    public class MySendListener implements SendListener {
        private final MyLeshanServer server;

        public MySendListener(MyLeshanServer server) {
            this.server = server;
        }

        @Override
        public void dataReceived(Registration registration,
                                         TimestampedLwM2mNodes data, SendRequest request) {
            System.out.println("dataReceived from: " + registration.getEndpoint());
            System.out.println("data: " + data);
        }

        @Override
        public void onError(Registration registration,
                                 String errorMessage, Exception error) {
          System.out.println("Unable to handle Send Request from: " + registration.getEndpoint());
          System.out.println(errorMessage);
          System.out.println(error);
        }
    }
}

