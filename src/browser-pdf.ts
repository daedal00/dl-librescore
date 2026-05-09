import fs from "fs";
import os from "os";
import path from "path";
import { spawn } from "child_process";

const HELPER_PATH = path.resolve(__dirname, "../scripts/seleniumbase_pdf.py");

export const exportPdfViaBrowser = async (
    scoreUrl: string,
    setText?: (str: string) => void
): Promise<{ title: string; fileName: string; pdfData: Buffer }> => {
    const outPath = path.join(
        os.tmpdir(),
        `dl-librescore-${Date.now()}-${Math.random().toString(16).slice(2)}.pdf`
    );

    const { stdout } = await new Promise<{ stdout: string }>((resolve, reject) => {
        const child = spawn("uv", ["run", HELPER_PATH, scoreUrl, outPath], {
            stdio: ["ignore", "pipe", "pipe"],
        });

        let stdout = "";
        let stderr = "";

        child.stdout.on("data", (chunk) => {
            const text = chunk.toString();
            stdout += text;
            const lines = text
                .split(/\r?\n/g)
                .map((line) => line.trim())
                .filter(Boolean);
            const last = lines[lines.length - 1];
            if (last && !last.startsWith("{")) {
                setText?.(last);
            }
        });

        child.stderr.on("data", (chunk) => {
            stderr += chunk.toString();
        });

        child.on("error", (err) => {
            if ((err as NodeJS.ErrnoException).code === "ENOENT") {
                reject(
                    new Error(
                        "Browser PDF fallback requires 'uv' (Python package manager). " +
                            "Install it from https://docs.astral.sh/uv/getting-started/installation/"
                    )
                );
            } else {
                reject(err);
            }
        });
        child.on("close", (code) => {
            if (code === 0) {
                resolve({ stdout });
            } else {
                reject(new Error(stderr.trim() || stdout.trim() || `uv exited with code ${code}`));
            }
        });
    });

    const metaLine = stdout
        .split(/\r?\n/g)
        .map((line) => line.trim())
        .filter((line) => line.startsWith("{"))
        .pop();

    if (!metaLine) {
        throw new Error("SeleniumBase helper did not return PDF metadata");
    }

    const meta = JSON.parse(metaLine) as {
        title: string;
        fileName: string;
    };
    const pdfData = await fs.promises.readFile(outPath);
    await fs.promises.unlink(outPath).catch(() => undefined);

    return {
        title: meta.title,
        fileName: meta.fileName,
        pdfData,
    };
};
