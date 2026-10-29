// Local-only stand-in. The fixture is a projection of the real public response.
const http = require('http');
const fs = require('fs');
const path = require('path');

class CkanMockServer {
  constructor() {
    this.payload = JSON.parse(fs.readFileSync(
      path.resolve(__dirname, '../../../tests/fixtures/ckan_package_show.json'), 'utf8'));
  }

  handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    if (req.method !== 'GET' || !['/api/3/action/package_show', '/ckan/api/3/action/package_show'].includes(url.pathname)) {
      res.writeHead(501, {'Content-Type': 'application/json'});
      return res.end(JSON.stringify({error: 'Endpoint not modelled'}));
    }
    res.writeHead(200, {'Content-Type': 'application/json'});
    if (url.searchParams.get('id') !== this.payload.result.name) {
      return res.end(JSON.stringify({success: false, error: {__type: 'Not Found Error'}}));
    }
    res.end(JSON.stringify(this.payload));
  }

  start() {
    http.createServer(this.handle.bind(this)).listen(process.env.PORT || 4500);
  }
}
new CkanMockServer().start();
