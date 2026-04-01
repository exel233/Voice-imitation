const { spawn } = require("node:child_process");
const path = require("node:path");
const electronBinary = require("electron");

const mode = process.argv[2] || "development";
const env = { ...process.env, NODE_ENV: mode };
delete env.ELECTRON_RUN_AS_NODE;

const child = spawn(electronBinary, ["."], {
  cwd: path.resolve(__dirname, ".."),
  stdio: "inherit",
  env,
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
