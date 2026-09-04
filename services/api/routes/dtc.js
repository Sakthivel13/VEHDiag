'use strict';
/** VEHDiag — /api/v1/dtc: DTC library, search, decode. */

const { ok } = require('../lib/http');
const { lookup, LIBRARY } = require('../../../diagnostics/dtc');

function mount(router) {
  router.get('/api/v1/dtc', async (req, res) => {
    const q = String(req.query.q || '').trim().toUpperCase();
    let codes = Object.keys(LIBRARY);
    if (q) codes = codes.filter((c) => c.startsWith(q) || c.includes(q));
    const limit = Math.min(parseInt(req.query.limit || '50', 10) || 50, 200);
    const out = codes.slice(0, limit).map((c) => lookup(c));
    ok(res, { dtcs: out, total: codes.length, librarySize: Object.keys(LIBRARY).length });
  });

  router.get('/api/v1/dtc/:code', async (req, res) => {
    const code = req.params.code.toUpperCase();
    ok(res, { dtc: lookup(code) });
  });
}

module.exports = { mount };
