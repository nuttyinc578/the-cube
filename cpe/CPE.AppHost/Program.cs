using Aspire.Hosting.ApplicationModel;

var builder = DistributedApplication.CreateBuilder(args);

var packagedGoCache = Path.GetFullPath(Path.Combine(builder.AppHostDirectory, "..", "go-cache", "bin", "cpe-go-cache.exe"));
var goCacheExecutable = File.Exists(packagedGoCache)
    ? builder.AddExecutable(
        "cpe-go-cache",
        packagedGoCache,
        "../go-cache",
        "--host",
        "127.0.0.1",
        "--port",
        "4311")
    : builder.AddExecutable(
        "cpe-go-cache",
        "go",
        "../go-cache",
        "run",
        ".",
        "--host",
        "127.0.0.1",
        "--port",
        "4311");

var goCache = goCacheExecutable
    .WithHttpEndpoint(port: 4311, targetPort: 4311, name: "http", env: "CPE_GO_CACHE_PORT", isProxied: false)
    .WithExternalHttpEndpoints();

var goCacheEndpoint = goCache.GetEndpoint("http");

var nodeBridge = builder
    .AddExecutable(
        "cpe-node-bridge",
        "node",
        "../node-bridge",
        "server.js",
        "--host",
        "127.0.0.1",
        "--port",
        "4310")
    .WithHttpEndpoint(port: 4310, targetPort: 4310, name: "http", env: "CPE_NODE_PORT", isProxied: false)
    .WithEnvironment("CPE_NODE_HOST", "127.0.0.1")
    .WithEnvironment("CPE_GO_CACHE_URL", goCacheEndpoint)
    .WithExternalHttpEndpoints();

var bridgeEndpoint = nodeBridge.GetEndpoint("http");

var packagedGame = Path.GetFullPath(Path.Combine(builder.AppHostDirectory, "..", "..", "The Cube Beta Fall.exe"));
var gameExecutable = File.Exists(packagedGame)
    ? builder.AddExecutable("the-cube-beta-fall", packagedGame, "../..")
    : builder.AddExecutable(
        "the-cube-beta-fall",
        "py",
        "../..",
        "-3.10",
        "the_cube_beta_summer.py");

gameExecutable
    .WithEnvironment("CPE_BRIDGE_URL", bridgeEndpoint)
    .WithEnvironment("CPE_GO_CACHE_URL", goCacheEndpoint)
    .WithEnvironment(context =>
    {
        context.EnvironmentVariables["CPE_ASPIRE_IP"] = bridgeEndpoint.Property(EndpointProperty.Host);
        context.EnvironmentVariables["CPE_NODE_PORT"] = bridgeEndpoint.Property(EndpointProperty.Port);
        context.EnvironmentVariables["CPE_GO_CACHE_PORT"] = goCacheEndpoint.Property(EndpointProperty.Port);
    });

builder.Build().Run();