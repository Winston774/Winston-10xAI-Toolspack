import http from 'node:http';
import worker from '../dist/server/index.js';
const port = Number(process.env.PORT || 4321);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error('PORT must be an integer from 1 to 65535.'); process.exit(1);
}
const server = http.createServer(async (req, res) => {
  try {
    const aborter = new AbortController();
    res.on('close', () => { if (!res.writableEnded) aborter.abort(); });
    const request = new Request(`http://127.0.0.1:${port}${req.url}`, {
      method: req.method, headers: req.headers, signal: aborter.signal,
      ...(!['GET','HEAD'].includes(req.method) ? { body: req, duplex: 'half' } : {}),
    });
    const response = await worker.fetch(request);
    res.writeHead(response.status, Object.fromEntries(response.headers)); res.end(Buffer.from(await response.arrayBuffer()));
  } catch { res.writeHead(500); res.end('Preview unavailable'); }
});
server.on('error', error => {
  console.error(error.code === 'EADDRINUSE' ? `Port ${port} is already in use. Close your previous instance or set PORT to another local port.` : 'Unable to start local preview.');
  process.exitCode = 1;
});
server.listen(port, '127.0.0.1', () => console.log(`Local: http://127.0.0.1:${port}/`));
