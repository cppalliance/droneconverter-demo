
FROM ubuntu:18.04
ARG OSVERSION=18.04
ARG CLANGVERSION=7.0.1
ARG CLANGDOWNLOAD=https://releases.llvm.org/7.0.1/clang+llvm-$CLANGVERSION-x86_64-linux-gnu-ubuntu-$OSVERSION.tar.xz
RUN apt-get -o Acquire::Retries=3 update && DEBIAN_FRONTEND=noninteractive apt-get -y install tzdata && apt-get -o Acquire::Retries=3 install -y sudo software-properties-common wget curl apt-transport-https git make apt-file sudo unzip libssl-dev build-essential autotools-dev autoconf automake g++ libc++-helpers python python-pip ruby cpio gcc-multilib g++-multilib pkgconf python3 python3-pip ccache libpython-dev && rm -rf /var/lib/apt/lists/*
RUN for i in {1..3}; do apt-add-repository ppa:git-core/ppa && break || sleep 2; done
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 -y install git && rm -rf /var/lib/apt/lists/*
RUN wget $CLANGDOWNLOAD && mkdir -p /usr/local/clang+llvm-$CLANGVERSION && tar xf clang+llvm-$CLANGVERSION-x86_64-linux-gnu-ubuntu-$OSVERSION.tar.xz -C  /usr/local/clang+llvm-$CLANGVERSION --strip-components=1
ENV PATH="/usr/local/clang+llvm-$CLANGVERSION/bin:$PATH"
RUN dpkg --add-architecture i386
RUN pip3 install cmake
# rearrange later
# RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 -y install _ && rm -rf /var/lib/apt/lists/*
