# CPE Java client

This dependency-free Java client sends commands to the Node bridge. Node converts the command into a numeric `CPE/1` line; the permanently embedded Python CPE runtime then applies it to Pymunk, Pygame, and IPE.

Compile:

```powershell
javac -d cpe/java-client/out cpe/java-client/src/main/java/com/nuttyinc/cpe/CpeClient.java
```

With the Aspire stack running, send a polygon command:

```powershell
java -cp cpe/java-client/out com.nuttyinc.cpe.CpeClient 127.0.0.1 4310 spawn
```

The final argument can also be `burst`, `clear`, `gravity`, `pause`, or `resume`.

Use the API from Java:

```java
CpeClient cpe = new CpeClient("127.0.0.1", 4310);
cpe.spawnBox(400, 80, 30, 222, 108, 39);
cpe.burst(400, 160, 50);
```

The client sends data commands only. It does not transmit or execute arbitrary Java or Python source code.
