// Neural Posthouse dictation helper.
// Local Windows desktop speech recognition (System.Speech, in-process engine).
// - Runs hidden, only when the user presses the microphone button.
// - Emits one JSON object per line on stdout (interim / final / level / state).
// - Never writes audio to disk and never contacts a network service.
// - Releases the microphone when "stop" arrives on stdin, stdin closes
//   (parent exited), or the bounded session time elapses.
using System;
using System.Globalization;
using System.Speech.Recognition;
using System.Text;
using System.Threading;

public static class NeuralDictation
{
    static readonly object Gate = new object();

    static void Emit(string json)
    {
        lock (Gate)
        {
            try { Console.Out.WriteLine(json); Console.Out.Flush(); } catch { }
        }
    }

    static string Q(string s)
    {
        if (s == null) return "null";
        var b = new StringBuilder("\"");
        foreach (char c in s)
        {
            switch (c)
            {
                case '"': b.Append("\\\""); break;
                case '\\': b.Append("\\\\"); break;
                case '\n': b.Append("\\n"); break;
                case '\r': b.Append("\\r"); break;
                case '\t': b.Append("\\t"); break;
                default:
                    if (c < 0x20) b.AppendFormat("\\u{0:x4}", (int)c); else b.Append(c);
                    break;
            }
        }
        return b.Append('"').ToString();
    }

    static void Error(string code, string message)
    {
        Emit("{\"type\":\"error\",\"code\":" + Q(code) + ",\"message\":" + Q(message) + "}");
    }

    static int Probe()
    {
        var list = SpeechRecognitionEngine.InstalledRecognizers();
        var sb = new StringBuilder("{\"type\":\"probe\",\"recognizers\":[");
        for (int i = 0; i < list.Count; i++)
        {
            if (i > 0) sb.Append(',');
            sb.Append("{\"id\":" + Q(list[i].Id) + ",\"culture\":" + Q(list[i].Culture.Name) + ",\"name\":" + Q(list[i].Description) + "}");
        }
        sb.Append("]}");
        Emit(sb.ToString());
        return 0;
    }

    static int Run(string culture, int maxSeconds, string wavPath)
    {
        RecognizerInfo info = null;
        foreach (var r in SpeechRecognitionEngine.InstalledRecognizers())
        {
            if (info == null) info = r;
            if (!String.IsNullOrEmpty(culture) && r.Culture.Name.Equals(culture, StringComparison.OrdinalIgnoreCase)) { info = r; break; }
        }
        if (info == null)
        {
            Error("no-recognizer", "No Windows desktop speech recognizer is installed for dictation.");
            return 3;
        }
        SpeechRecognitionEngine engine = null;
        var done = new ManualResetEvent(false);
        string reason = "stopped";
        try
        {
            engine = new SpeechRecognitionEngine(info);
            engine.LoadGrammar(new DictationGrammar());
            // A WAV path is only used by automated engine checks (synthesized speech);
            // the desktop app always uses the default microphone.
            if (!String.IsNullOrEmpty(wavPath)) engine.SetInputToWaveFile(wavPath);
            else
            {
                try { engine.SetInputToDefaultAudioDevice(); }
                catch (Exception ex)
                {
                    Error("no-microphone", "Windows did not provide a default microphone: " + ex.Message);
                    return 4;
                }
            }
            engine.SpeechHypothesized += (s, e) => Emit("{\"type\":\"interim\",\"text\":" + Q(e.Result.Text) + "}");
            engine.SpeechDetected += (s, e) => Emit("{\"type\":\"speech_start\"}");
            engine.SpeechRecognized += (s, e) => Emit("{\"type\":\"final\",\"text\":" + Q(e.Result.Text) + ",\"confidence\":" + e.Result.Confidence.ToString("0.###", CultureInfo.InvariantCulture) + "}");
            engine.SpeechRecognitionRejected += (s, e) => Emit("{\"type\":\"rejected\"}");
            engine.AudioStateChanged += (s, e) => Emit("{\"type\":\"audio\",\"state\":" + Q(e.AudioState.ToString()) + "}");
            long lastTicks = 0; int lastBucket = -1;
            engine.AudioLevelUpdated += (s, e) =>
            {
                long now = DateTime.UtcNow.Ticks; int bucket = e.AudioLevel / 10;
                if (now - lastTicks >= TimeSpan.TicksPerMillisecond * 250 && bucket != lastBucket)
                {
                    lastTicks = now; lastBucket = bucket;
                    Emit("{\"type\":\"level\",\"level\":" + e.AudioLevel.ToString(CultureInfo.InvariantCulture) + "}");
                }
            };
            engine.RecognizeCompleted += (s, e) =>
            {
                if (e.Error != null) { Error("recognizer", e.Error.Message); reason = "error"; }
                done.Set();
            };
            engine.RecognizeAsync(RecognizeMode.Multiple);
            Emit("{\"type\":\"listening\",\"engine\":" + Q(info.Description) + ",\"culture\":" + Q(info.Culture.Name) + ",\"offline\":true}");
            var reader = new Thread(() =>
            {
                try
                {
                    string line;
                    while ((line = Console.In.ReadLine()) != null)
                    {
                        if (line.Trim().Equals("stop", StringComparison.OrdinalIgnoreCase)) break;
                    }
                }
                catch { }
                try { engine.RecognizeAsyncStop(); } catch { done.Set(); }
            });
            reader.IsBackground = true;
            // A test WAV finishes at RecognizeCompleted; inherited stdin may already
            // be closed. Only live microphone sessions use stdin as an owner lease.
            if (String.IsNullOrEmpty(wavPath)) reader.Start();
            if (!done.WaitOne(TimeSpan.FromSeconds(Math.Max(5, maxSeconds)))) reason = "time-limit";
        }
        catch (Exception ex)
        {
            Error("recognizer", ex.Message);
            reason = "error";
        }
        finally
        {
            if (engine != null)
            {
                try { engine.RecognizeAsyncCancel(); } catch { }
                try { engine.SetInputToNull(); } catch { }
                try { engine.Dispose(); } catch { }
            }
            Emit("{\"type\":\"stopped\",\"reason\":" + Q(reason) + "}");
        }
        return 0;
    }

    public static int Main(string[] args)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        string culture = "", wav = ""; int maxSeconds = 300; bool probe = false;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--probe") probe = true;
            else if (args[i] == "--culture" && i + 1 < args.Length) culture = args[++i];
            else if (args[i] == "--max-seconds" && i + 1 < args.Length) Int32.TryParse(args[++i], out maxSeconds);
            else if (args[i] == "--wav" && i + 1 < args.Length) wav = args[++i];
        }
        try { return probe ? Probe() : Run(culture, maxSeconds, wav); }
        catch (Exception ex) { Error("speech-unavailable", ex.Message); return 2; }
    }
}
