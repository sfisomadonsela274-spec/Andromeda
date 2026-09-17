#!/usr/bin/env node
/**
 * Puppeteer Automation Runner for Jimmy & Andromeda
 * Provides robust headless browser automation, UI testing, DOM extraction, and screenshots.
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

async function main() {
    let inputData = null;

    // Support input via CLI arg (--input '<json>') or stdin
    const inputArgIndex = process.argv.indexOf('--input');
    if (inputArgIndex !== -1 && process.argv[inputArgIndex + 1]) {
        try {
            inputData = JSON.parse(process.argv[inputArgIndex + 1]);
        } catch (e) {
            console.error(JSON.stringify({ status: 'error', message: `Invalid JSON in --input: ${e.message}` }));
            process.exit(1);
        }
    } else if (process.argv[2] && !process.argv[2].startsWith('--')) {
        // Direct command line: action url [optional_param]
        inputData = {
            command: process.argv[2],
            url: process.argv[3],
            extra: process.argv[4]
        };
    } else {
        // Read from stdin
        const stdinBuffer = fs.readFileSync(0, 'utf-8');
        if (stdinBuffer.trim()) {
            try {
                inputData = JSON.parse(stdinBuffer);
            } catch (e) {
                console.error(JSON.stringify({ status: 'error', message: `Invalid stdin JSON: ${e.message}` }));
                process.exit(1);
            }
        }
    }

    if (!inputData || (!inputData.url && !inputData.query)) {
        console.error(JSON.stringify({
            status: 'error',
            message: 'Missing input payload or target. Format: { command: "test_flow"|"navigate"|"screenshot"|"pdf"|"eval"|"youtube_search"|"play_media", url or query }'
        }));
        process.exit(1);
    }

    const command = inputData.command || 'navigate';
    const url = inputData.url;
    const timeout = inputData.timeout || 30000;
    const viewport = inputData.viewport || { width: 1280, height: 800 };

    let browser = null;
    try {
        browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        });

        const page = await browser.newPage();
        await page.setViewport(viewport);

        // Collect console errors & warnings
        const consoleLogs = [];
        page.on('console', msg => {
            consoleLogs.push({ type: msg.type(), text: msg.text() });
        });

        const result = {
            status: 'success',
            command,
            url,
            logs: consoleLogs
        };

        if (command === 'navigate') {
            const response = await page.goto(url, { waitUntil: inputData.waitUntil || 'domcontentloaded', timeout });
            result.title = await page.title();
            result.httpStatus = response ? response.status() : null;

            // Extract readable text and summary of interactive elements
            const pageData = await page.evaluate(() => {
                // Remove scripts, styles, and noscripts
                const clone = document.body.cloneNode(true);
                const toRemove = clone.querySelectorAll('script, style, noscript, svg');
                toRemove.forEach(el => el.remove());

                const text = clone.innerText.replace(/\s+/g, ' ').trim();
                const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => h.innerText.trim()).filter(Boolean);
                const buttons = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
                const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({ text: a.innerText.trim(), href: a.getAttribute('href') })).slice(0, 20);

                return {
                    text: text.slice(0, 4000),
                    headings: headings.slice(0, 10),
                    buttons: buttons.slice(0, 15),
                    links
                };
            });

            result.pageData = pageData;

            if (inputData.screenshot_path) {
                const outPath = path.resolve(inputData.screenshot_path);
                fs.mkdirSync(path.dirname(outPath), { recursive: true });
                await page.screenshot({ path: outPath, fullPage: !!inputData.fullPage });
                result.screenshot = outPath;
            }

        } else if (command === 'screenshot') {
            await page.goto(url, { waitUntil: 'networkidle2', timeout });
            const outPath = path.resolve(inputData.output_path || `screenshot_${Date.now()}.png`);
            fs.mkdirSync(path.dirname(outPath), { recursive: true });

            if (inputData.selector) {
                const el = await page.$(inputData.selector);
                if (!el) throw new Error(`Selector "${inputData.selector}" not found on page`);
                await el.screenshot({ path: outPath });
            } else {
                await page.screenshot({ path: outPath, fullPage: !!inputData.fullPage });
            }

            result.screenshot = outPath;
            result.title = await page.title();

        } else if (command === 'test_flow') {
            await page.goto(url, { waitUntil: inputData.waitUntil || 'domcontentloaded', timeout });
            const actions = inputData.actions || [];
            const actionLogs = [];

            for (let i = 0; i < actions.length; i++) {
                const act = actions[i];
                const actType = act.action || act.type;
                const sel = act.selector;
                const val = act.value || '';
                const stepTimeout = act.timeout || 5000;

                try {
                    if (actType === 'click') {
                        await page.waitForSelector(sel, { timeout: stepTimeout, visible: true });
                        await page.click(sel);
                        actionLogs.push({ step: i + 1, action: 'click', selector: sel, status: 'ok' });
                    } else if (actType === 'fill' || actType === 'type') {
                        await page.waitForSelector(sel, { timeout: stepTimeout, visible: true });
                        // Clear existing text if requested
                        if (act.clear !== false) {
                            await page.click(sel, { clickCount: 3 });
                            await page.keyboard.press('Backspace');
                        }
                        await page.type(sel, String(val));
                        actionLogs.push({ step: i + 1, action: 'fill', selector: sel, value: val, status: 'ok' });
                    } else if (actType === 'press') {
                        await page.keyboard.press(val || 'Enter');
                        actionLogs.push({ step: i + 1, action: 'press', key: val || 'Enter', status: 'ok' });
                    } else if (actType === 'wait_for') {
                        await page.waitForSelector(sel, { timeout: stepTimeout, visible: true });
                        actionLogs.push({ step: i + 1, action: 'wait_for', selector: sel, status: 'ok' });
                    } else if (actType === 'wait') {
                        const waitMs = parseInt(val || act.duration || 1000, 10);
                        await new Promise(r => setTimeout(r, waitMs));
                        actionLogs.push({ step: i + 1, action: 'wait', duration: waitMs, status: 'ok' });
                    } else if (actType === 'assert_text') {
                        await page.waitForSelector(sel, { timeout: stepTimeout });
                        const text = await page.$eval(sel, el => el.innerText || el.textContent || '');
                        if (!text.toLowerCase().includes(String(val).toLowerCase())) {
                            throw new Error(`Assertion failed: expected "${val}" in ${sel}, found "${text.trim()}"`);
                        }
                        actionLogs.push({ step: i + 1, action: 'assert_text', selector: sel, expected: val, found: text.trim(), status: 'passed' });
                    } else if (actType === 'assert_element') {
                        await page.waitForSelector(sel, { timeout: stepTimeout, visible: true });
                        actionLogs.push({ step: i + 1, action: 'assert_element', selector: sel, status: 'passed' });
                    } else if (actType === 'screenshot') {
                        const sPath = path.resolve(val || act.path || `flow_step_${i + 1}.png`);
                        fs.mkdirSync(path.dirname(sPath), { recursive: true });
                        await page.screenshot({ path: sPath });
                        actionLogs.push({ step: i + 1, action: 'screenshot', path: sPath, status: 'ok' });
                    } else if (actType === 'evaluate') {
                        const evalResult = await page.evaluate(val);
                        actionLogs.push({ step: i + 1, action: 'evaluate', result: evalResult, status: 'ok' });
                    } else {
                        actionLogs.push({ step: i + 1, action: actType, status: 'unknown_action' });
                    }
                } catch (stepErr) {
                    actionLogs.push({ step: i + 1, action: actType, selector: sel, status: 'failed', error: stepErr.message });
                    result.status = 'failed';
                    result.failedStep = i + 1;
                    result.error = stepErr.message;
                    result.actions = actionLogs;
                    console.log(JSON.stringify(result, null, 2));
                    await browser.close();
                    return;
                }
            }

            result.actions = actionLogs;
            result.title = await page.title();

        } else if (command === 'eval') {
            await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
            const script = inputData.script || inputData.extra || '() => document.title';
            const evalResult = await page.evaluate(new Function(`return (${script})();`));
            result.evalResult = evalResult;
            result.title = await page.title();

        } else if (command === 'pdf') {
            await page.goto(url, { waitUntil: 'networkidle0', timeout });
            const outPath = path.resolve(inputData.output_path || `page_${Date.now()}.pdf`);
            fs.mkdirSync(path.dirname(outPath), { recursive: true });
            await page.pdf({ path: outPath, format: inputData.format || 'A4', printBackground: true });
            result.pdf = outPath;
            result.title = await page.title();

        } else if (command === 'youtube_search') {
            const query = inputData.query || inputData.url;
            const searchUrl = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query);
            await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout });
            await page.waitForSelector('a#video-title', { timeout: 10000 });
            
            const topVideo = await page.evaluate(() => {
                const el = document.querySelector('a#video-title');
                if (!el) return null;
                const href = el.getAttribute('href') || '';
                const match = href.match(/v=([a-zA-Z0-9_-]{11})/);
                return {
                    title: el.innerText ? el.innerText.trim() : '',
                    href: href,
                    url: href.startsWith('http') ? href : ('https://www.youtube.com' + href),
                    videoId: match ? match[1] : null
                };
            });

            if (!topVideo) {
                throw new Error(`No YouTube video results found for "${query}"`);
            }

            result.video = topVideo;
            result.title = topVideo.title;
            result.url = topVideo.url;
            result.videoId = topVideo.videoId;

        } else if (command === 'play_media') {
            const query = inputData.query || inputData.url;
            const targetBrowser = inputData.browser || 'firefox';
            const searchUrl = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query);
            await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout });
            await page.waitForSelector('a#video-title', { timeout: 10000 });
            
            const topVideo = await page.evaluate(() => {
                const el = document.querySelector('a#video-title');
                if (!el) return null;
                const href = el.getAttribute('href') || '';
                const match = href.match(/v=([a-zA-Z0-9_-]{11})/);
                return {
                    title: el.innerText ? el.innerText.trim() : '',
                    href: href,
                    url: href.startsWith('http') ? href : ('https://www.youtube.com' + href),
                    videoId: match ? match[1] : null
                };
            });

            if (!topVideo) {
                throw new Error(`No YouTube video results found for "${query}"`);
            }

            const { spawn } = require('child_process');
            const playUrl = topVideo.url + (topVideo.url.includes('?') ? '&autoplay=1' : '?autoplay=1');
            
            let child = null;
            if (targetBrowser === 'firefox') {
                child = spawn('firefox', [playUrl], { detached: true, stdio: 'ignore', env: process.env });
                child.unref();
            } else {
                child = spawn('google-chrome', [playUrl, '--autoplay-policy=no-user-gesture-required'], { detached: true, stdio: 'ignore', env: process.env });
                child.unref();
            }

            result.video = topVideo;
            result.playUrl = playUrl;
            result.browserLaunched = targetBrowser;
            result.title = topVideo.title;
        }

        console.log(JSON.stringify(result, null, 2));
    } catch (err) {
        console.error(JSON.stringify({
            status: 'error',
            message: err.message,
            stack: err.stack
        }));
        process.exitCode = 1;
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

main();
