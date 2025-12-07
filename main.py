import streamlink
import sys
import os 
import json
import traceback


def info_to_text(stream_info, url):
    text = '#EXT-X-STREAM-INF:'
    if getattr(stream_info, "program_id", None):
        text += 'PROGRAM-ID=' + str(stream_info.program_id) + ','
    if getattr(stream_info, "bandwidth", None):
        text += 'BANDWIDTH=' + str(stream_info.bandwidth) + ','
    if getattr(stream_info, "codecs", None):
        codecs = stream_info.codecs
        if codecs:
            text += 'CODECS="'
            for i in range(len(codecs)):
                text += codecs[i]
                if i != len(codecs) - 1:
                    text += ','
            text += '",'
    if getattr(stream_info, "resolution", None) and stream_info.resolution.width:
        text += 'RESOLUTION=' + str(stream_info.resolution.width) + 'x' + str(stream_info.resolution.height)

    text += "\n" + url + "\n"
    return text


def build_from_multivariant(hls_stream):
    """
    multivariant varsa master ve best playlist üretir.
    Yoksa (None ise) (None, None) döner.
    """
    mv = getattr(hls_stream, "multivariant", None)
    if mv is None or not getattr(mv, "playlists", None):
        return None, None

    playlists = mv.playlists

    previous_res_height = 0
    master_text = ''
    best_text = ''

    for playlist in playlists:
        uri = playlist.uri
        info = playlist.stream_info

        # Sadece video akışları
        if getattr(info, "video", None) == "audio_only":
            continue

        sub_text = info_to_text(info, uri)

        if info.resolution and info.resolution.height > previous_res_height:
            master_text = sub_text + master_text
            best_text = sub_text
            previous_res_height = info.resolution.height
        else:
            master_text = master_text + sub_text

    if not master_text:
        return None, None

    version = mv.version
    header = ''
    if version:
        header = '#EXT-X-VERSION:' + str(version) + "\n"

    master_text = '#EXTM3U\n' + header + master_text
    best_text = '#EXTM3U\n' + header + best_text

    return master_text, best_text


def build_simple_best(best_stream):
    """
    multivariant yoksa (tek kalite .m3u8 gibi),
    tek URL'lik basit bir playlist üretir.
    """
    url = None
    try:
        url = best_stream.to_url()
    except Exception:
        url = getattr(best_stream, "url", None)

    if not url:
        return None, None

    text = '#EXTM3U\n' + url + '\n'
    # Hem master hem best aynı olsun
    return text, text


def main():
    print("=== Starting stream processing ===")
    
    # Loading config file
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    print(f"Loading config from: {config_file}")
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ ERROR loading config file: {e}")
        sys.exit(1)

    # Getting output options and creating folders
    folder_name = config["output"]["folder"]          # streams
    best_folder_name = config["output"]["bestFolder"] # best
    master_folder_name = config["output"]["masterFolder"]  # "" veya "master"

    current_dir = os.getcwd()
    root_folder = os.path.join(current_dir, folder_name)

    # masterFolder boşsa master'ları direkt root_folder'a yaz
    if master_folder_name:
        master_folder = os.path.join(root_folder, master_folder_name)
    else:
        master_folder = root_folder

    best_folder = os.path.join(root_folder, best_folder_name)
    
    print("Creating folders:")
    print(f"  Root:   {root_folder}")
    print(f"  Master: {master_folder}")
    print(f"  Best:   {best_folder}")
    
    os.makedirs(root_folder, exist_ok=True)
    os.makedirs(best_folder, exist_ok=True)
    if master_folder != root_folder:
        os.makedirs(master_folder, exist_ok=True)

    channels = config["channels"]
    print(f"\n=== Processing {len(channels)} channels ===\n")
    
    success_count = 0
    fail_count = 0

    for idx, channel in enumerate(channels, 1):
        slug = channel.get("slug", "unknown")
        url = channel.get("url", "")
        
        print(f"[{idx}/{len(channels)}] Processing: {slug}")
        print(f"  URL: {url}")
        
        try:
            streams = streamlink.streams(url)
            
            if not streams:
                print(f"  ⚠️  No streams found for {slug}")
                fail_count += 1
                continue
                
            if 'best' not in streams:
                print(f"  ⚠️  No 'best' stream found for {slug}")
                print(f"  Available streams: {list(streams.keys())}")
                fail_count += 1
                continue
            
            best_stream = streams['best']

            # Önce multivariant'tan üretmeyi dene
            master_text, best_text = build_from_multivariant(best_stream)

            # Olmazsa basit tek URL playlist üret
            if not master_text:
                master_text, best_text = build_simple_best(best_stream)

            if not master_text:
                print(f"  ⚠️  No content generated for {slug}")
                # Hatalı dosya varsa sil
                master_file_path = os.path.join(master_folder, channel["slug"] + ".m3u8")
                best_file_path = os.path.join(best_folder, channel["slug"] + ".m3u8")
                if os.path.isfile(master_file_path):
                    os.remove(master_file_path)
                if os.path.isfile(best_file_path):
                    os.remove(best_file_path)
                fail_count += 1
                continue

            master_file_path = os.path.join(master_folder, channel["slug"] + ".m3u8")
            best_file_path = os.path.join(best_folder, channel["slug"] + ".m3u8")

            with open(master_file_path, "w", encoding="utf-8") as master_file:
                master_file.write(master_text)

            with open(best_file_path, "w", encoding="utf-8") as best_file:
                best_file.write(best_text)
            
            print(f"  ✅ Success - Files created")
            success_count += 1
                
        except Exception as e:
            print(f"  ❌ ERROR processing {slug}: {str(e)}")
            print(traceback.format_exc())
            
            master_file_path = os.path.join(master_folder, channel["slug"] + ".m3u8")
            best_file_path = os.path.join(best_folder, channel["slug"] + ".m3u8")
            if os.path.isfile(master_file_path):
                os.remove(master_file_path)
            if os.path.isfile(best_file_path):
                os.remove(best_file_path)
            fail_count += 1
    
    print(f"\n=== Summary ===")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"Total: {len(channels)}")


if __name__=="__main__": 
    main()
