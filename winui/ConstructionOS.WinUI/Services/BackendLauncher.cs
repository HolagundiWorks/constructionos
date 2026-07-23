using System.Diagnostics;
using System.IO;
using System.Net.Sockets;

namespace ConstructionOS.WinUI.Services;

/// <summary>
/// Ensures the localhost Python backend is running before the shell loads (U6).
/// If it's already reachable, returns immediately. Otherwise — when
/// <see cref="AppSettings.AutoStartBackend"/> is on and the API is localhost — it
/// launches a **bundled sidecar** (`Backend\ACO.Backend.exe` next to the app, as
/// the MSIX package ships) or the configured dev command, then waits for the port.
/// Best-effort: if it can't start one, the shell just shows its offline page.
/// Never starts anything for a non-localhost API (a LAN/remote server).
/// </summary>
public static class BackendLauncher
{
    public static async Task EnsureAsync()
    {
        var s = AppSettings.Current;
        if (!s.AutoStartBackend) return;
        if (!Uri.TryCreate(s.BaseUrl, UriKind.Absolute, out var url)) return;
        if (url.Host is not ("127.0.0.1" or "localhost" or "::1")) return;
        var port = url.Port > 0 ? url.Port : 8080;

        if (await IsUpAsync(port)) return;

        var (cmd, args, dir) = Resolve(s, port);
        if (cmd is null) return;
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = cmd,
                Arguments = args,
                WorkingDirectory = dir,
                UseShellExecute = false,
                CreateNoWindow = true,
            });
        }
        catch
        {
            return;   // couldn't launch — offline page will guide the user
        }

        // Give it a few seconds to bind the port (db.init_db on first run).
        for (var i = 0; i < 20; i++)
        {
            if (await IsUpAsync(port)) return;
            await Task.Delay(400);
        }
    }

    // (fileName, arguments, workingDir) or (null, …) if nothing to launch.
    private static (string? Cmd, string Args, string Dir) Resolve(AppSettings s, int port)
    {
        var portArgs = $"--host 127.0.0.1 --port {port}";

        // 1) Bundled sidecar next to the app (packaged / MSIX).
        var baseDir = AppContext.BaseDirectory;
        foreach (var name in new[] { "ACO.Backend.exe", "aco-backend.exe", "web_main.exe" })
        {
            var p = Path.Combine(baseDir, "Backend", name);
            if (File.Exists(p)) return (p, portArgs, Path.GetDirectoryName(p)!);
        }

        // 2) Configured dev command (e.g. a python.exe + …\construction_app).
        if (!string.IsNullOrWhiteSpace(s.BackendCommand))
        {
            var dir = s.BackendWorkingDir ?? "";
            var hasScript = dir.Length > 0 && File.Exists(Path.Combine(dir, "web_main.py"));
            var args = hasScript ? $"web_main.py {portArgs}" : portArgs;
            return (s.BackendCommand, args, dir);
        }

        return (null, "", "");
    }

    private static async Task<bool> IsUpAsync(int port)
    {
        try
        {
            using var c = new TcpClient();
            var connect = c.ConnectAsync("127.0.0.1", port);
            var done = await Task.WhenAny(connect, Task.Delay(500));
            return done == connect && c.Connected;
        }
        catch
        {
            return false;
        }
    }
}
