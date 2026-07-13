# Set up the Spektrafilm darktable build on a new Windows PC

Build and run your custom darktable (with the **Spektrafilm** module + advanced-options
section) from your GitHub fork, and pin it to the taskbar. End to end this takes ~45–90 min,
mostly the first compile.

- **Fork / branch:** `https://github.com/leonnorth/darktable` , branch **`spektrafilm`**
- **What you get:** a from-source master build of darktable with the Spektrafilm iop,
  OpenCL-accelerated, launchable from a pinned taskbar icon.

> Paths below assume MSYS2 at `C:\msys64` (the standard install). If you can't install as
> admin, see **[No admin?](#no-admin)** and replace `C:\msys64` with `%USERPROFILE%\msys64`
> everywhere.

---

## Prerequisites
- Windows 10/11 x64, ~12 GB free disk, a working internet connection.
- A GPU with an OpenCL driver for acceleration (Intel/AMD/NVIDIA). It also runs CPU-only if not.
- Git for Windows (`git --version`). If missing: `winget install Git.Git`.

---

## Step 1 — Install MSYS2

1. Download and run the installer from <https://www.msys2.org> (installs to `C:\msys64`).
2. Open **“MSYS2 UCRT64”** from the Start menu (important: the *UCRT64* shell, not MSYS/MINGW64).
3. Update the base system (run twice; the first pass may close the terminal — reopen and repeat):
   ```bash
   pacman -Syuu --noconfirm
   pacman -Syuu --noconfirm
   ```

## Step 2 — Install toolchain + dependencies

In the **UCRT64** shell:
```bash
pacman -S --needed --noconfirm base-devel git intltool po4a
pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-{cc,cmake,gcc-libs,ninja,omp}
pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-{libxslt,python-jsonschema,curl,drmingw,exiv2,gettext,gmic,graphicsmagick,gtk3,icu,imath,iso-codes,lcms2,lensfun,libavif,libarchive,libgphoto2,libheif,libjpeg-turbo,libjxl,libpng,libraw,librsvg,libsecret,libtiff,libwebp,libxml2,lua54,openexr,openjpeg2,osm-gps-map,portmidi,potrace,pugixml,SDL2,sqlite3,webp-pixbuf-loader,zlib}
```
OpenCL needs no extra package here — darktable ships the headers as a submodule and loads
your GPU driver's `OpenCL.dll` at runtime.

## Step 3 — Clone your fork (with submodules)

In the **UCRT64** shell:
```bash
cd ~                                   # or wherever you keep repos, e.g. /c/repos
git clone --branch spektrafilm https://github.com/leonnorth/darktable.git
cd darktable
git submodule update --init            # RawSpeed, LibRaw, OpenCL headers, etc. (a few hundred MB)
git remote add upstream https://github.com/darktable-org/darktable.git   # for future rebases
```

## Step 4 — Build darktable

From the `darktable` folder in the **UCRT64** shell:
```bash
./build.sh --prefix /opt/darktable --build-type Release --build-generator Ninja --install
```
This compiles ~1000 targets (first time is the slow part) and installs to
`C:\msys64\opt\darktable`. When it finishes you'll see `Installing: .../darktable.exe`.

Verify OpenCL sees your GPU (optional but recommended):
```bash
/opt/darktable/bin/darktable-cltest.exe -d opencl 2>&1 | grep -iE "FINALLY|DEVICE:"
```
You want a line ending in `AVAILABLE and ENABLED`. (First run compiles the kernel cache — up to ~1 min.)

## Step 5 — Install the Spektrafilm data pack

The module ships only the algorithms; the film/paper profiles + spectral LUT are a small
(~12 MB) data pack that must live in darktable's config dir
(`%LOCALAPPDATA%\darktable\spektrafilm`). Two ways:

### Easy: copy the pack from your other PC
Copy the whole folder
`C:\repos\DT_Spektrafilm\dt-config\spektrafilm\` (from the first PC — it contains
`pack.json`, `spectra_lut.f32`, `profiles\`) to `%LOCALAPPDATA%\darktable\spektrafilm\` on
this PC. Done — skip to Step 6.

### From scratch: regenerate it (self-contained)
Needs Python **3.13** (the spektrafilm exporter requires `~=3.13`; not 3.14). In **PowerShell**:
```powershell
winget install --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
$py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
& $py -m venv "$env:USERPROFILE\.spektra-venv"
$venv = "$env:USERPROFILE\.spektra-venv\Scripts\python.exe"
& $venv -m pip install --upgrade pip
& $venv -m pip install --no-deps "git+https://github.com/andreavolpato/spektrafilm@dev"
& $venv -m pip install numpy scipy colour-science matplotlib exiv2 lensfunpy rawpy numba openimageio opt-einsum scikit-image
```
Get the exporter script `spektrafilm_export_data.py` — either copy it from
`C:\repos\DT_Spektrafilm\forum-patches\` on your other PC, or download it:
<https://discuss.pixls.us/uploads/short-url/iXXGrDIXTjg2uY2X0Q9ZuZQQzSa.py> (save as
`spektrafilm_export_data.py`). Then run it into the config dir:
```powershell
& $venv "$env:USERPROFILE\Downloads\spektrafilm_export_data.py" -o "$env:LOCALAPPDATA\darktable\spektrafilm"
```
Success prints `wrote ...\pack.json` and `copied NN profiles`.

## Step 6 — First run & verify

From the **UCRT64** shell:
```bash
/opt/darktable/bin/darktable.exe
```
Import a photo, open it in **darkroom**, click the module-search magnifier (bottom of the
right panel), type **`spektrafilm`**, enable it — you should get the film look. Expand
**“advanced options”** to see the extra controls. Close darktable.

> ⚠️ **If you also run official/stable darktable on this PC:** this is a newer *master* build
> and will upgrade the shared catalog (`%LOCALAPPDATA%\darktable\library.db`) to a schema
> stable darktable can't open. To keep them separate, always launch this build with a
> dedicated config dir, e.g. add `--configdir "%USERPROFILE%\dt-spektra"` to the launcher in
> Step 7 (and put the data pack in `%USERPROFILE%\dt-spektra\spektrafilm` instead).

## Step 7 — Pinned taskbar icon

The build needs `C:\msys64\ucrt64\bin` on PATH to find its DLLs, so we use a tiny launcher.
Run this once in **PowerShell** to create the launcher + a Desktop shortcut with darktable's icon:

```powershell
$dtRoot = "C:\msys64"          # <-- change to "$env:USERPROFILE\msys64" if you did the no-admin install
$launcher = "$env:USERPROFILE\run-darktable-spektrafilm.cmd"
@"
@echo off
set "PATH=$dtRoot\ucrt64\bin;%PATH%"
start "" "$dtRoot\opt\darktable\bin\darktable.exe" %*
"@ | Set-Content -Encoding ASCII -Path $launcher

$sc = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\darktable (spektrafilm).lnk")
$sc.TargetPath       = "cmd.exe"
$sc.Arguments        = "/c `"$launcher`""
$sc.IconLocation     = "$dtRoot\opt\darktable\bin\darktable.exe,0"
$sc.WindowStyle      = 7        # launcher window starts minimized
$sc.WorkingDirectory = "$env:USERPROFILE"
$sc.Save()
Write-Host "Created shortcut on your Desktop."
```

Then pin it:
1. Double-click the new **“darktable (spektrafilm)”** shortcut on your Desktop to confirm it opens.
2. While darktable is running, **right-click its taskbar icon → Pin to taskbar**.
   (In Win11 you can also right-click the Desktop shortcut → *Show more options → Pin to taskbar*.)

From now on, click the pinned icon to launch your Spektrafilm darktable anytime.

> **Zero-flash alternative** (no launcher window at all): permanently add `ucrt64\bin` to your
> user PATH, then pin a plain shortcut to `darktable.exe`:
> ```powershell
> $p = [Environment]::GetEnvironmentVariable('Path','User')
> [Environment]::SetEnvironmentVariable('Path', "$p;C:\msys64\ucrt64\bin", 'User')
> ```
> (Log out/in for it to take effect. Downside: MSYS2 tools/DLLs are now on your PATH globally.)

---

## Updating later (pull new changes + rebuild)

When you push updates to `spektrafilm` (or rebase it on newer upstream), on this PC:
```bash
cd ~/darktable                         # your clone
git pull                               # fetch your fork's spektrafilm branch
git submodule update --init            # in case submodule pins moved
./build.sh --prefix /opt/darktable --build-type Release --build-generator Ninja --install
```
The pinned icon keeps working — it points at `/opt/darktable`, which `--install` refreshes.
After editing the OpenCL kernel (`spektrafilm.cl`) specifically, clear the kernel cache once:
delete the `cached_v6_kernels_*` folder under `%LOCALAPPDATA%\darktable\cache`.

To pull in new upstream darktable releases:
```bash
git fetch upstream
git rebase upstream/master             # your commit replays on top; conflicts are rare
git push --force-with-lease origin spektrafilm
```

---

## <a name="no-admin"></a>No admin rights?

Install MSYS2 without admin to your home folder, then use `%USERPROFILE%\msys64` in place of
`C:\msys64` everywhere above (including `$dtRoot` in Step 7). In **PowerShell**:
```powershell
Invoke-WebRequest https://repo.msys2.org/distrib/msys2-x86_64-latest.exe -OutFile "$env:TEMP\msys2.exe"
& "$env:TEMP\msys2.exe" in --confirm-command --accept-messages --root "$env:USERPROFILE\msys64"
```
Then start the UCRT64 shell via `%USERPROFILE%\msys64\ucrt64.exe` and continue from Step 1's
`pacman` updates.

## Troubleshooting
- **“libgtk-3-0.dll not found” when double-clicking:** `ucrt64\bin` isn't on PATH — use the
  Step 7 launcher (or the PATH alternative), don't run `darktable.exe` directly.
- **OpenCL not enabled:** update your GPU driver; re-check with `darktable-cltest.exe -d opencl`.
  darktable still works on CPU, just slower.
- **Module missing / “data pack not found”:** confirm Step 5 put `pack.json` etc. in the
  config dir darktable actually uses (default `%LOCALAPPDATA%\darktable\spektrafilm`, or your
  `--configdir` path if you set one).
- **Build fails on a temp file / permission error:** make sure you're in the **UCRT64** shell
  (not a bare `cmd`), which sets a writable temp dir.
