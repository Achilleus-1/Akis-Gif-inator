// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Achilleus
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("Aki's Gif-inator")]
[assembly: AssemblyDescription("Native local video-to-GIF desktop app")]
[assembly: AssemblyCompany("Achilleus")]
[assembly: AssemblyProduct("Aki's Gif-inator")]
[assembly: AssemblyCopyright("Copyright (c) 2026 Achilleus")]
[assembly: AssemblyVersion("1.1.0.0")]
[assembly: AssemblyFileVersion("1.1.0.0")]

internal static class Launcher
{
    // Windows argv quoting, including embedded quotes and trailing backslashes.
    private static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { slashes++; continue; }
            if (character == '"') result.Append('\\', slashes * 2 + 1);
            else result.Append('\\', slashes);
            result.Append(character); slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        bool smoke = Array.IndexOf(args, "--smoke-test") >= 0;
        string python = Path.Combine(root, "runtime", smoke ? "python.exe" : "pythonw.exe");
        string source = Path.Combine(root, "app.py");
        if (!File.Exists(python) || !File.Exists(source))
        {
            MessageBox.Show("The app runtime is missing. Run Aki's Gif-inator Setup again.", "Aki's Gif-inator", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        try
        {
            var command = new StringBuilder("-B " + Quote(source));
            foreach (string argument in args) command.Append(" " + Quote(argument));
            var start = new ProcessStartInfo(python, command.ToString());
            start.WorkingDirectory = root; start.UseShellExecute = false; start.CreateNoWindow = true;
            using (var process = Process.Start(start))
            {
                if (smoke) { process.WaitForExit(); return process.ExitCode; }
            }
            return 0;
        }
        catch (Exception)
        {
            MessageBox.Show("The app could not start. Run Setup again to repair its runtime.", "Aki's Gif-inator", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
