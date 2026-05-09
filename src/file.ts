/* eslint-disable no-extend-native */
/* eslint-disable @typescript-eslint/no-unsafe-return */

import md5 from "md5";
import { getFetch } from "./utils";
import { auths } from "./file-magics";

export type FileType = "img" | "mp3" | "midi";

const getSuffix = async (
    scoreUrl: string,
    _fetch = getFetch()
): Promise<string | null> => {
    let suffixUrls: string[] = [];
    const jsReg =
        /link.+?href=["'](https:\/\/musescore\.com\/static\/public\/build\/musescore.*?(?:_es6)?\/20.+?\.js)["']/g;

    if (scoreUrl !== "") {
        try {
            const response = await _fetch(scoreUrl);
            const text = await response.text();
            suffixUrls = [...text.matchAll(jsReg)].map((match) => match[1]);
        } catch {
            // If the landing page itself fails, we have no suffix to extract
            return null;
        }
    } else if (typeof document !== "undefined") {
        suffixUrls = [...document.head.innerHTML.matchAll(jsReg)].map(
            (match) => match[1]
        );
    }

    // MuseScore changes minification frequently; try several patterns.
    const patterns = [
        /"([^"]+)"\)\.substr\(0,4\)/,
        /"([^"]+)"\)\.slice\(0,4\)/,
        /"([^"]+)"\)[^.]*\.(?:substr|slice)\(0,4\)/,
    ];

    for (const url of suffixUrls) {
        try {
            const response = await _fetch(url);
            const text = await response.text();
            for (const pattern of patterns) {
                const match = text.match(pattern);
                if (match) {
                    return match[1];
                }
            }
        } catch {
            // Ignore individual bundle failures
        }
    }

    return null;
};

const getApiUrl = (id: number, type: FileType, index: number): string => {
    return `/api/jmuse?id=${id}&type=${type}&index=${index}`;
};

const getApiAuth = async (
    id: number,
    type: FileType,
    index: number,
    scoreUrl: string
): Promise<string> => {
    const code = `${id}${type}${index}${await getSuffix(scoreUrl)}`;
    return md5(code).slice(0, 4);
};

let imgInProgress = false;

const getApiAuthNetwork = async (
    type: FileType,
    index: number
): Promise<string> => {
    if (typeof document === "undefined") {
        throw new Error("Cannot derive auth token in Node.js runtime");
    }

    let numPages = 0;
    let pageCooldown = 25;
    if (!auths[type + index]) {
        try {
            switch (type) {
                case "midi": {
                    const fsBtn = document.querySelector(
                        'button[title="Toggle Fullscreen"]'
                    ) as HTMLButtonElement;
                    if (!fsBtn) {
                        // mobile device
                        document
                            .querySelector("button[title='Open Mixer']")
                            ?.click();
                        const observer = new MutationObserver(() => {
                            if (
                                document.querySelector(
                                    "body > article[role='dialog']"
                                )
                            ) {
                                let audioSources = document.querySelector(
                                    "body > article[role='dialog'] select"
                                );

                                if (audioSources !== null) {
                                    audioSources.querySelector(
                                        "option[value='0']"
                                    )?.selected = true;

                                    audioSources.dispatchEvent(
                                        new Event("change")
                                    );
                                }
                                document
                                    .querySelector(
                                        "article[role='dialog'] header > button"
                                    )
                                    ?.click();
                            }
                        });
                        observer.observe(document.body, {
                            childList: true,
                            subtree: true,
                        });
                    } else {
                        const el =
                            fsBtn.parentElement?.parentElement?.querySelector(
                                "button"
                            ) as HTMLButtonElement;
                        el.click();
                    }
                    break;
                }
                case "mp3": {
                    const el = document.querySelector(
                        'button[title="Toggle Play"]'
                    ) as HTMLButtonElement;
                    if (!el) {
                        // mobile device
                        document.querySelector("#scorePlayButton")?.click();
                    } else {
                        el.click();
                    }
                    break;
                }
                case "img": {
                    if (!imgInProgress) {
                        imgInProgress = true;
                        let parentDiv = document.querySelector(
                            "#jmuse-scroller-component"
                        )!;

                        numPages = parentDiv.children.length - 3;
                        let i = 0;

                        function scrollToNextChild() {
                            let childDiv = parentDiv.children[i];
                            if (childDiv) {
                                childDiv.scrollIntoView();
                            }

                            i++;

                            if (i < numPages) {
                                setTimeout(scrollToNextChild, pageCooldown);
                            }
                        }

                        scrollToNextChild();
                    }
                    imgInProgress = false;
                    break;
                }
            }
        } catch (err) {
            console.error(err);
            throw Error;
        }
    }

    try {
        return new Promise((resolve, reject) => {
            let timer = setTimeout(
                () => {
                    reject(new Error("token timeout"));
                },
                type === "img"
                    ? numPages * pageCooldown * 2 + 2100
                    : 5 * 1000 /* 5s */
            );

            // Check the auths object periodically
            let interval = setInterval(() => {
                if (auths.hasOwnProperty(type + index)) {
                    clearTimeout(timer);
                    clearInterval(interval);
                    setTimeout(
                        () => {
                            resolve(auths[type + index]);
                        },
                        // long delay for images to give time for them to load fully
                        type === "img" ? 2000 : 100
                    );
                }
            }, 100);
        });
    } catch {
        console.error(type, "token timeout");
        throw Error;
    }
};

export const getFileUrl = async (
    id: number,
    type: FileType,
    scoreUrl = "",
    index = 0,
    _fetch = getFetch(),
    setText?: (str: string) => void,
    pageCount?: number
): Promise<string> => {
    const url = getApiUrl(id, type, index);
    const suffix = await getSuffix(scoreUrl);

    if (setText && pageCount) {
        const percent = Math.round(((index + 1) / pageCount) * 83);
        setText(`${percent}%`);
    }

    // Build auth candidates: extracted suffix first, then hardcoded fallback.
    const auths: string[] = [];
    if (suffix) {
        auths.push(md5(`${id}${type}${index}${suffix}`).slice(0, 4));
    }
    auths.push(md5(`${id}${type}${index}9654,4e`).slice(0, 4));

    let lastResponse: Response | undefined;
    for (const auth of auths) {
        const r = await _fetch(url, {
            headers: {
                Authorization: auth,
            },
        });
        lastResponse = r;
        if (r.ok) {
            const { info } = await r.json();
            return info.url as string;
        }
    }

    // In a browser we can observe UI interactions to steal the token.
    if (typeof document !== "undefined") {
        const auth = await getApiAuthNetwork(type, index);
        if (type === "img" && index === 0) {
            // auth is the URL for the first page
            const r = await _fetch(auth);
            if (r.ok) {
                const { info } = await r.json();
                return info.url as string;
            }
        } else {
            const r = await _fetch(url, {
                headers: {
                    Authorization: auth,
                },
            });
            if (r.ok) {
                const { info } = await r.json();
                return info.url as string;
            }
        }
    }

    // Nothing worked.
    const status = lastResponse?.status ?? "unknown";
    throw new Error(
        `Failed to authorize ${type} download for score ${id} (HTTP ${status}). MuseScore likely changed auth or blocked automated access.`
    );
};
