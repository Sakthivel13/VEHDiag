'use strict';
/** VEHDiag — /api/v1/ecus: ECU definition registry (public definitions only). */

const { ok } = require('../lib/http');
const { registry } = require('../../../diagnostics/ecu');

function mount(router) {
  router.get('/api/v1/ecus', async (req, res) => {
    const kind = req.query.kind;
    const defs = registry.list().filter((d) => !kind || d.kind === kind);
    ok(res, {
      ecus: defs.map((d) => ({
        id: d.ecuId, name: d.name, kind: d.kind, protocol: d.protocol,
        can: d.can,
        didCount: d.dids ? Object.keys(d.dids).length : 0,
        supportedServices: d.supportedServices,
      })),
    });
  });

  router.get('/api/v1/ecus/:id', async (req, res) => {
    const d = registry.get(req.params.id);
    if (!d) return ok(res, { ecu: null }, 404);
    ok(res, { ecu: d });
  });
}

module.exports = { mount };
