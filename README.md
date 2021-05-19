# dns-tls-proxy

Objective - write simple DNS proxy, listening at TCP/53,
which will receive plain TCP DNS request,
query upstream CloudFlare DNS 1.1.1.1:853 via TLS,
and return result to the client.

Initial attempt was done using low-level socket() approach
can be seen in `socket-trivial/` directory
scaling such solution require threading or multi-process,
gathering metrics using `prometheus-client` library is pretty difficult.

So, I've tried to use Python asyncio for handling multiple incoming requests.

### Security concerns while deploying as microservice

Validate upstream server CloudFlare certificate periodically.

Run service in container under non-privileged user on non-privileged port,
deploy as k8s `Service` to forward privileged port 53 to non-privileged port 8853.

```
kind: Service
apiVersion: v1
metadata:
  name: dns-tls-proxy
spec:
  selector:
    app: dns-tls-proxy
  ports:
  - protocol: TCP
    port: 53
    targetPort: 8853
```    


Introduce rate-limit per client IPs, using token-bucket algoritm for example.

### Integrate in distributed, microservices-oriented and containerized architecture

Analyze requirements, possible deploy using DaemonSet is needed.

Add service discovery, either using home-grown (like Consul-based) service discovery.
For k8s we can use app-level annotations.

Implement health-check endpoint
Expose cpu/mem/usage, requests by status in metrics

### Improvements

  * validate DNS queries/requests
  * refactor - create classes, split into different files, get rid of global variables 
  * add cpu/mem metrics
  * improve app-level metrics - parse DNS queries and responses, add metrics for successfull
and failed queries
  * cache results according to TTL
  * analyze top X requests, like google.com and keep results for them pre-resolved, with periodic update every TTL seconds
  * implement upstream connection pooling to reduce resolve time by removing TLS handshake for every request

## Build/Run/Test

### Build using docker

```docker build -t dns-tls-proxy:test .```

### Run

Open console, run it with 53/TCP port exposed for serving DNS queries and 5000 for `/metrics`

```docker run --rm --name dns-tls-proxy -p 53:53 -p 5000:5000 -t dns-tls-proxy:test```

### Test

in another shell window, generate some queries
```
for i in seq {1..100};do dig @127.0.0.1 -p 53 +tcp aa$i.com;done
```

Metrics can be observed by running `curl localhost:5000/metrics` from new shell window

Alerts are needed at least for:
- higher than usual latencies like 100+ ms for 90-percentile
- high queries rates per IP/port pair per second (needs support in the code)

