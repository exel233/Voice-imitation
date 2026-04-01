const { spawn } = require("node:child_process");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = process.cwd();

function hasPackage(python, packageName) {
  const result = spawnSync(
    python,
    ["-c", `import importlib.util; raise SystemExit(0 if importlib.util.find_spec('${packageName}') else 1)`],
    { cwd: root, stdio: "ignore" },
  );
  return result.status === 0;
}

function resolveSystemPython() {
  const candidates = process.platform === "win32"
    ? [
        process.env.PYTHON,
        process.env.PYTHON_HOME && path.join(process.env.PYTHON_HOME, "python.exe"),
        process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python310", "python.exe"),
        "python",
      ]
    : [process.env.PYTHON, "python3", "python"];

  for (const candidate of candidates.filter(Boolean)) {
    if (candidate.includes(path.sep) && !fs.existsSync(candidate)) {
      continue;
    }
    const result = spawnSync(candidate, ["-c", "import sys; print(sys.executable)"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    if (result.status === 0) {
      return result.stdout.trim() || candidate;
    }
  }
  return "python";
}

function resolvePython() {
  const venvPython = process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");

  const systemPython = resolveSystemPython();

  if (fs.existsSync(venvPython)) {
    const venvHasTts = hasPackage(venvPython, "TTS");
    const systemHasTts = hasPackage(systemPython, "TTS");
    if (venvHasTts || !systemHasTts) {
      return venvPython;
    }
    return systemPython;
  }

  return systemPython;
}

function getArgValue(args, flagName, fallback) {
  const index = args.indexOf(flagName);
  if (index === -1 || index === args.length - 1) {
    return fallback;
  }
  return args[index + 1];
}

function findPortOwners(port) {
  if (process.platform === "win32") {
    const result = spawnSync("netstat", ["-ano"], { encoding: "utf8", cwd: root });
    if (result.status !== 0) {
      return [];
    }
    return result.stdout
      .split(/\r?\n/)
      .filter((line) => line.includes(`:${port}`) && line.includes("LISTENING"))
      .map((line) => line.trim().split(/\s+/))
      .map((parts) => Number(parts[parts.length - 1]))
      .filter((value, index, array) => Number.isFinite(value) && array.indexOf(value) === index);
  }

  const result = spawnSync("lsof", ["-ti", `tcp:${port}`], { encoding: "utf8", cwd: root });
  if (result.status !== 0) {
    return [];
  }
  return result.stdout
    .split(/\r?\n/)
    .map((line) => Number(line.trim()))
    .filter((value, index, array) => Number.isFinite(value) && array.indexOf(value) === index);
}

function stopProcess(pid) {
  if (process.platform === "win32") {
    const result = spawnSync("taskkill", ["/PID", String(pid), "/F"], {
      cwd: root,
      stdio: "ignore",
    });
    return result.status === 0;
  }
  const result = spawnSync("kill", ["-9", String(pid)], {
    cwd: root,
    stdio: "ignore",
  });
  return result.status === 0;
}

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function freePortIfNeeded(port) {
  const owners = findPortOwners(port);
  if (!owners.length) {
    return;
  }

  console.log(`[run_backend] Port ${port} is already in use by PID(s): ${owners.join(", ")}. Attempting cleanup.`);
  for (const pid of owners) {
    const stopped = stopProcess(pid);
    console.log(`[run_backend] ${stopped ? "Stopped" : "Could not stop"} PID ${pid}.`);
  }

  let remaining = [];
  for (let attempt = 0; attempt < 10; attempt += 1) {
    sleep(300);
    remaining = findPortOwners(port);
    if (!remaining.length) {
      return;
    }
  }

  if (remaining.length) {
    console.error(`[run_backend] Port ${port} is still in use by PID(s): ${remaining.join(", ")}.`);
    process.exit(1);
  }
}

const python = resolvePython();
const extraArgs = process.argv.slice(2);
const filteredArgs =
  process.env.VOICE_STUDIO_DISABLE_RELOAD === "1"
    ? extraArgs.filter((arg) => arg !== "--reload")
    : extraArgs;
const port = getArgValue(filteredArgs, "--port", "8765");

freePortIfNeeded(port);

const child = spawn(
  python,
  ["-m", "uvicorn", "backend.app.main:app", ...filteredArgs],
  {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  },
);

child.on("exit", (code) => {
  process.exit(code ?? 0);
});
