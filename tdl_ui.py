import subprocess
import gradio as gr
import os

TDL_COMMAND = r"C:\Softwares\tdl_Windows_64bit\tdl.exe dl"
DEFAULT_DOWNLOAD_DIR = r"C:\Users\zhoub\Downloads\Telegram Desktop\【视频】"


def add_task(tasks, url, count):
    if not url:
        return tasks, "", [[t["url"], t["count"]] for t in tasks]
    tasks.append({"url": url, "count": max(1, int(count))})
    return tasks, "", [[t["url"], t["count"]] for t in tasks]


def download_all(tasks, download_dir):
    if not tasks:
        return "请先添加下载任务"
    if not download_dir:
        download_dir = DEFAULT_DOWNLOAD_DIR

    results = []
    for task in tasks:
        url = task["url"]
        count = task["count"]
        if 'comment=' in url:
            url_base = url.split("comment=")[0]
            start = int(url.split("comment=")[1])
            stop = start + count
            for i in range(start, stop):
                full_url = f"{url_base}comment={i}"
                result = subprocess.run(
                    f'{TDL_COMMAND} -u "{full_url}"',
                    capture_output=True,
                    shell=True
                )
                try:
                    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
                    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
                except Exception:
                    stdout = str(result.stdout)
                    stderr = str(result.stderr)
                output = stdout + stderr
                results.append(f"[{full_url}]\n{output}")
        else:
            base_url = url.split("?")[0]
            sub_url = ("/").join(base_url.split("/")[0:-1])
            sub_index = int(base_url.split("/")[-1])
            command = f'{TDL_COMMAND} --continue -d "{download_dir}"'
            for i in range(count):
                command += f' -u "{sub_url}/{sub_index + i}"'
            result = subprocess.run(command, capture_output=True, shell=True)
            try:
                stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
                stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            except Exception:
                stdout = str(result.stdout)
                stderr = str(result.stderr)
            output = stdout + stderr
            results.append(f"[{base_url} x{count}]\n{output}")
    return "\n" + "-" * 50 + "\n".join(results)


def clear_tasks():
    return [], "", []


with gr.Blocks(title="TDL Downloader") as demo:
    gr.Markdown("# TDL Downloader")
    gr.Markdown("添加多个 Telegram URL 批量下载")

    tasks_state = gr.State([])

    with gr.Row():
        url_input = gr.Textbox(label="URL", placeholder="输入 Telegram 链接", scale=3)
        count_input = gr.Number(label="数量", value=1, minimum=1, step=1, scale=1)
        add_btn = gr.Button("添加任务", scale=1)

    with gr.Row():
        download_dir_input = gr.Textbox(
            label="下载目录",
            value=DEFAULT_DOWNLOAD_DIR,
            scale=3
        )

    task_list = gr.DataFrame(
        headers=["URL", "数量"],
        datatype=["str", "number"],
        label="下载任务列表",
        interactive=False
    )

    with gr.Row():
        download_btn = gr.Button("开始下载", variant="primary", scale=2)
        clear_btn = gr.Button("清空列表", scale=1)

    output = gr.Textbox(label="下载状态", lines=15)

    add_btn.click(
        fn=add_task,
        inputs=[tasks_state, url_input, count_input],
        outputs=[tasks_state, url_input, task_list]
    )

    download_btn.click(
        fn=download_all,
        inputs=[tasks_state, download_dir_input],
        outputs=output
    )

    clear_btn.click(
        fn=clear_tasks,
        outputs=[tasks_state, output, task_list]
    )

demo.launch(server_name="0.0.0.0", server_port=7860)
