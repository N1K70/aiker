import React, { useEffect, useMemo, useState } from "react";
import { render, Box, Text, useApp, useInput } from "ink";
import { spawn } from "node:child_process";

const MAX_LOG_LINES = 28;
const INTERACTIVE_TTY = Boolean(process.stdin.isTTY && process.stdout.isTTY);

function Banner() {
  const lines = [
    "   ___    _ _              ",
    "  / _ |  (_) |_____ ____   ",
    " / __ | / /  '_/ -_) __/   ",
    "/_/ |_|/_/_/\\_\\\\__/_/      ",
    " Internal Recon Console    ",
  ];

  return (
    <Box flexDirection="column" marginBottom={1}>
      {lines.map((line) => (
        <Text key={line} color="green">
          {line}
        </Text>
      ))}
      <Text color="gray">Metasploit-style Ink UI for Aiker</Text>
    </Box>
  );
}

function App() {
  const { exit } = useApp();
  const [target, setTarget] = useState("");
  const [submittedTarget, setSubmittedTarget] = useState("");
  const [status, setStatus] = useState("idle");
  const [logs, setLogs] = useState<string[]>([]);
  const [exitCode, setExitCode] = useState<number | null>(null);

  useInput(
    (input, key) => {
      if (key.ctrl && input.toLowerCase() === "c") {
        exit();
      }
      if (input.toLowerCase() === "q") {
        exit();
      }
      if (status === "idle") {
        if (key.return) {
          const normalized = target.trim();
          if (!normalized) {
            return;
          }
          setLogs([]);
          setSubmittedTarget(normalized);
          setStatus("running");
          return;
        }
        if (key.backspace || key.delete) {
          setTarget((prev) => prev.slice(0, -1));
          return;
        }
        if (input && !key.escape && !key.tab) {
          setTarget((prev) => `${prev}${input}`);
        }
        return;
      }
      if (status === "done" && input.toLowerCase() === "r") {
        setTarget("");
        setSubmittedTarget("");
        setLogs([]);
        setExitCode(null);
        setStatus("idle");
      }
    },
    { isActive: INTERACTIVE_TTY },
  );

  useEffect(() => {
    if (status !== "running" || !submittedTarget) {
      return;
    }

    const args = [
      "-m",
      "aiker",
      "workflow",
      "--target",
      submittedTarget,
      "--max-tools",
      "10",
      "--show-raw",
    ];

    const child = spawn("python", args, { stdio: ["ignore", "pipe", "pipe"] });

    const appendLogs = (chunk: Buffer) => {
      const text = chunk.toString();
      const lines = text
        .split(/\r?\n/)
        .map((line) => line.trimEnd())
        .filter((line) => line.length > 0);
      if (lines.length === 0) {
        return;
      }
      setLogs((prev) => [...prev, ...lines].slice(-MAX_LOG_LINES));
    };

    child.stdout.on("data", appendLogs);
    child.stderr.on("data", appendLogs);

    child.on("close", (code) => {
      setExitCode(code);
      setStatus("done");
    });

    return () => {
      child.kill();
    };
  }, [status, submittedTarget]);

  const statusLine = useMemo(() => {
    if (status === "idle") {
      return "Type target and press Enter to launch workflow.";
    }
    if (status === "running") {
      return `Running workflow against ${submittedTarget}...`;
    }
    return `Workflow finished with exit code ${exitCode ?? "unknown"}. Press "r" to run again.`;
  }, [status, submittedTarget, exitCode]);

  return (
    <Box flexDirection="column" padding={1}>
      <Banner />

      <Box marginBottom={1}>
        <Text color="cyan">Status: </Text>
        <Text>{statusLine}</Text>
      </Box>

      {!INTERACTIVE_TTY && (
        <Box marginBottom={1}>
          <Text color="yellow">
            Non-interactive terminal detected. Run this command in a regular terminal to use keyboard input.
          </Text>
        </Box>
      )}

      {status === "idle" && (
        <Box>
          <Text color="yellow">Target IP/URL: </Text>
          <Text color="white">{target || "_"}</Text>
        </Box>
      )}

      {(status === "running" || status === "done") && (
        <Box flexDirection="column" borderStyle="round" borderColor="green" paddingX={1}>
          <Text color="magenta">Live Activity</Text>
          {logs.length === 0 && <Text color="gray">No logs yet...</Text>}
          {logs.map((line, index) => (
            <Text key={`${index}-${line}`} wrap="truncate-end">
              {line}
            </Text>
          ))}
        </Box>
      )}

      <Box marginTop={1}>
        <Text color="gray">Controls: Enter run | q quit | r rerun after completion</Text>
      </Box>
    </Box>
  );
}

render(<App />);
