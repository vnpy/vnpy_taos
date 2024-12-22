docker run -d -v ~/taos/data:/var/lib/taos -v ~/taos/log:/var/log/taos -p 6030:6030 -p 6041:6041 -p 6043-6060:6043-6060 -p 6043-6060:6043-6060/udp tdengine/tdengine
