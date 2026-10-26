# The Cube Beta Launcher 1.0.0

Standalone launcher, separate from CPE Flasher. It does not rewrite the existing game or execute its Python scripts while checking loader state.

## Run

Open **Cube Beta Launcher.exe** (Windows build in `dist`). From source, run `python "Cube Beta Launcher.py"`. The launcher only requires Python 3.11+ with Tkinter; game packages contain their own runtime.

Choose **Refresh versions**, enter an instance name such as `halloween`, choose a version, and **Download / Install**. Press **Play** to start that instance. **Update** installs the selected release, not necessarily the newest; select the version you want first. Updates keep the complete previous instance under `backups` and preserve settings and userdata. Close the game before updating. Games started outside the launcher are not tracked: close them too.

Storage defaults to `%LOCALAPPDATA%/Nuttyinc/CubeLauncher`, not Codex or the working directory. Use `--data-dir PATH` before the command for a portable/custom location. Instances are independent; this launcher does not import or overwrite arbitrary existing game directories.

## CLI

```powershell
& '.\dist\Cube Beta Launcher.exe' versions
& '.\dist\Cube Beta Launcher.exe' install halloween 6.4.0
& '.\dist\Cube Beta Launcher.exe' instances
& '.\dist\Cube Beta Launcher.exe' status halloween
& '.\dist\Cube Beta Launcher.exe' play halloween
& '.\dist\Cube Beta Launcher.exe' update halloween 6.4.0
```

The console-enabled build supports both GUI and CLI. `python -m cube_launcher` is equivalent from source. No shell command strings are evaluated.

## Download and update safeguards

- Only published stable releases from `nuttyinc578/the-cube`, with portable ZIP or standalone game EXE and a GitHub SHA-256 asset digest. Installers, source-only releases and expired nightly artifacts are omitted. Versions 5.0 and older are unsupported.
- HTTPS with restricted redirect hosts, transfer/expanded-size and file-count limits, whole-download hash verification, validated archive paths and no ZIP symlinks/encrypted entries. Staged packages must contain one game EXE.
- Download failures leave the instance unchanged. Updates stage first, then move the existing instance to backup; a failed promotion restores it. Failed staging is retained for inspection, not executed.
- Unlocked, partially unlocked, unreadable or missing CPELoader state blocks updates for CPELoader-equipped editions. Legacy editions without CPELoader can update. The older Nuttymod unlocked-update bypass does not bypass this launcher policy.
- Fresh verified portable packages get a locked initial CPELoader state in staging if they omit one. Existing instance state is never automatically reset or relocked.
- Cross-launcher operation lock and game process tracking prevent overlapping operations. A stale `operation.lock` is not auto-deleted: close all launchers and games before manually removing it after a crash.
- These safeguards are not antivirus or a guarantee against malicious local users. Digests verify correspondence to the GitHub asset, not independent publisher signatures. Only run releases you trust. Editing/deleting loader files can invalidate local policy; this is not an OS security boundary.
- Backups are retained, never automatically erased. Manual recovery: close all launchers/games, move the current instance outside `instances`, then move the desired complete backup into `instances` with the original instance name. Do not merge a backup into a modified instance.

## Nuttyinc Cloud with AWS Cognito

**Create account on website** opens your supplied Cognito `/signup` link, including the CloudFront redirect and `email openid phone` scopes. This website registration flow does not mark the launcher signed in. After completing signup, return to the launcher and use **Sign in with Nuttyinc Cloud**, which retains its PKCE-protected localhost callback and only requests `openid email`. Launcher sign-in still requires the localhost callback to be registered in Cognito.

The launcher now defaults to your Cognito domain `https://ca-central-1kqtmazcpv.auth.ca-central-1.amazoncognito.com` and public app client `q2u1oorqn5lt2v89abisrg7rv`. Existing nonempty custom settings are preserved. The Sign in button opens Cognito's managed login; the separate Create account on website button opens your website signup flow if self-registration is enabled.

**Required AWS change:** add `http://localhost:8765/callback` to this app client's allowed callback URLs. You may keep the existing `https://d84l1y8p4kdic.cloudfront.net` callback for the website. The launcher cannot use that website callback to complete its local session. Enable scopes `openid` and `email`; the launcher does not request `phone` or `profile`. Authorization-code grant and a public client without a secret are required. This configuration has not been tested with a real account yet.

Account sign-in is optional and does not enable cloud saves or multiplayer identity yet. No AWS resources are automatically provisioned. Configure your AWS account first; Cognito usage can incur charges. Use AWS Console, not AWS access keys pasted into the launcher.

1. Create a Cognito user pool, with an appropriate email sign-in/verification policy and user recovery/MFA settings for your service.
2. Create a **public app client without a client secret**. Enable authorization-code grant only, scopes `openid`, `email`, `profile`, and the Cognito user pool identity provider.
3. Create an AWS Cognito managed-login domain, for example `https://YOUR-PREFIX.auth.ca-central-1.amazoncognito.com`. The launcher currently supports AWS-provided Cognito domains, not custom domains.
4. Register the exact callback URL `http://localhost:8765/callback`. AWS permits localhost HTTP for testing; production desktop deployment needs a reviewed native-app callback strategy. This initial launcher uses a fixed localhost development callback; port 8765 must be free.
5. Paste the HTTPS domain and public app client ID in launcher **Settings**, then Save. Click **Sign in with Nuttyinc Cloud**. The system browser handles passwords, signup and verification; the launcher uses authorization code + S256 PKCE and a random state, then confirms the user through Cognito userInfo.

Sign-in has a three-minute timeout. Tokens/passwords are not written to disk; the account badge lasts for the launcher session only. **Clear launcher sign-in** clears the badge, not the browser's Cognito session. Configure AWS's privacy/retention and your service disclosures before offering accounts publicly: using Cognito means account data is processed by AWS even though this launcher does not upload game saves.

AWS references: [Authorization endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html), [token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html), [userInfo endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/userinfo-endpoint.html).

## Build and checks

```powershell
python -m unittest test_cube_launcher -v
python 'Cube Beta Launcher.py' --data-dir build/launcher-qa --self-test
python -m PyInstaller --noconfirm --clean --onefile --console --name 'Cube Beta Launcher' 'Cube Beta Launcher.py'
```

The existing game's code and packaging are unchanged. Launcher 1.0.0 is a separate first build, not a new game version. Live account integration requires your deployed Cognito configuration and must be verified before public launch.
