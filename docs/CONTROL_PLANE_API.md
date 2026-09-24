# AI Assurance Control Plane API

Base path: `/v1/control`

## Public

- `GET /health`
- `GET /protocol/manifest`
- `POST /organizations/bootstrap`
- `POST /verify/passport`

## Authenticated

- `GET /organization`
- `POST /credentials`
- `GET /credentials`
- `POST /credentials/{key_id}/revoke`
- `POST /projects`
- `POST /assets`
- `GET /assets/{asset_id}`
- `POST /assets/{asset_id}/versions`
- `POST /assets/{asset_id}/dependencies`
- `GET /assets/{asset_id}/timeline`
- `GET /assets/{asset_id}/dependencies`
- `GET /assets/{asset_id}/assurance`
- `GET /assets/{asset_id}/graph`
- `POST /assets/{asset_id}/assure`
- `GET /assets/{asset_id}/trust/{version_id}`
- `POST /assets/{asset_id}/versions/{version_id}/deployment-check`
- `POST /assets/{asset_id}/versions/{version_id}/runtime-check`
- `POST /assets/{asset_id}/versions/{version_id}/revoke`
- `POST /policies`
- `GET /policies`
- `GET /policies/{policy_id}`
- `POST /policies/bind`
- `GET /assurance/{assurance_id}`
- `GET /assurance/{assurance_id}/passport`
- `GET /assets/{asset_id}/provenance/{assurance_id}`
- `GET /assets/{asset_id}/version-diff/{from_version}/{to_version}`

All authenticated resources are checked against the organization associated with the API key.
