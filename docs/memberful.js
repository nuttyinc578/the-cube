// Memberful owns the account overlay. Ordinary HTTPS links also work without JS.
(function(c) {
  var script = document.createElement("script");
  script.src = "https://js.memberful.com/embed.js";
  script.onload = function() { Memberful.setup(c); };
  document.head.appendChild(script);
})({ site: ["https://the-cube-beta-marketplace.memberful.com"] });
