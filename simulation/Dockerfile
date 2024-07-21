FROM ubuntu:latest

# Set the frontend to noninteractive to avoid debconf issues
ENV DEBIAN_FRONTEND=noninteractive

# Enable i386 architecture
RUN dpkg --add-architecture i386

RUN apt-get update -y
RUN apt-get install -y apt-utils iproute2 net-tools iptables iputils-ping dnsutils tio vim traceroute

# Install 32-bit libraries
RUN apt-get install -y libc6:i386 libstdc++6:i386 libc6-i386

# Clean up APT when done to reduce image size
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*
