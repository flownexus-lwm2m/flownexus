package com.example;

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
import org.eclipse.leshan.core.node.TimestampedLwM2mNodes;
import org.eclipse.leshan.core.link.lwm2m.LwM2mLink;
import org.eclipse.leshan.core.node.LwM2mNode;
import org.eclipse.leshan.core.node.LwM2mResource;
import org.eclipse.leshan.server.registration.Registration;
import org.eclipse.leshan.server.registration.RegistrationListener;
import org.eclipse.leshan.server.registration.RegistrationUpdate;
import org.eclipse.leshan.server.observation.ObservationListener;
import org.eclipse.leshan.server.californium.endpoint.CaliforniumServerEndpointsProvider;

import java.util.Collection;
import java.nio.ByteBuffer;

public class MyLeshanServer {

	private static LeshanServer server;

	public static void main(String[] args) {
		LeshanServerBuilder builder = new LeshanServerBuilder();
		
		builder.setEndpointsProviders(new CaliforniumServerEndpointsProvider());
		server = builder.build();
		server.start();
		
		server.getRegistrationService().addListener(new MyRegistrationListener());
		server.getObservationService().addListener(new MyObservationListener());
		server.getSendService().addListener(new MySendListener());
		
		Runtime.getRuntime().addShutdownHook(new Thread() {
			@Override
			public void run() {
				server.stop();
			}
		});
		
		System.out.println("Leshan server started");
	}

	private static class MyRegistrationListener implements RegistrationListener {

		@Override
		public void registered(Registration registration, Registration previousReg,
									  Collection<Observation> previousObsersations) {
			System.out.println("new device: " + registration.getEndpoint());

			/* Discover resources on the client*/
			LwM2mLink[] res;
			try {
				DiscoverResponse discoverResponse = server.send(registration, new DiscoverRequest(3));
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

	private static class MyObservationListener implements ObservationListener {

		@Override
		public void cancelled(Observation observation) {
		}

		@Override
		// TODO: this is just a demo, we should check the type of the content
		// and convert it to the appropriate type.
		// In Addition, we shoud create a new class, running in a separate thread, that
		// sends the data to the rest backend.
		public void onResponse(SingleObservation observation, Registration registration,
									  ObserveResponse response) {
			//System.out.println("onResponse (single): " + response);

			/* Print the content */
			LwM2mNode content = response.getContent();
			if (content instanceof LwM2mResource) {
				LwM2mResource resource = (LwM2mResource) content;
				byte[] value = (byte[]) resource.getValue();
					if(value.length == 8) {
						double temperature = ByteBuffer.wrap(value).getDouble();
						System.out.println("Temperature from " + registration.getEndpoint() + ": " + temperature);
					}
			}
		}

		@Override
		public void onResponse(CompositeObservation observation, Registration registration,
									  ObserveCompositeResponse response) {
			System.out.println("onResponse (composite): " + registration.getEndpoint());
			System.out.println("onResponse (composite): " + response);
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

	private static class MySendListener implements SendListener {

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
