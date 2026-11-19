# NVDA Controller Client

`nvdaControllerClient.dll` from NV Access, unmodified, used by `shared/uia_notify.py` to have NVDA speak a chat reply or a finished batch without moving focus (#409, #410). NVDA ignores UI Automation notifications from wx windows, which aren't native UIA windows, so without this NVDA said nothing.

- **Source:** https://download.nvaccess.org/releases/2026.2/nvda_2026.2_controllerClient.zip
  (SHA-256 of the zip: `510736f021aefa33378076fa342a4524b586bc1c6b096db9479af42b28aac649`)
- **Version:** NVDA 2026.2 controller client
- **Files:**
  - `x64/nvdaControllerClient.dll`, SHA-256 `598b7ec3dc469814f571275929f676ce73834c469fbdb359a06fd4db4e0fc866`
  - `arm64/nvdaControllerClient.dll`, SHA-256 `6faaa1dd82bae2ae953bd14f5206fef63b8932d9a3cb4578fe027ec794f7918e`
- **License:** GNU LGPL 2.1, in `license.txt`. The library is redistributed unmodified; its source is at https://github.com/nvaccess/nvda (`nvdaHelper/client`).

The DLL must match the architecture of the process that loads it, not NVDA's, so an x64 ImageDescriber on ARM64 Windows uses `x64/`. To update it, download the newer release's `_controllerClient.zip` from NV Access, replace both DLLs, and update the hashes above.
