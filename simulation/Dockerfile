FROM debian:latest

# Set the frontend to noninteractive to avoid debconf issues
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -y
RUN apt-get install -y apt-utils iproute2 net-tools iptables iputils-ping dnsutils tio vim traceroute procps

# Clean up APT when done to reduce image size
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*
