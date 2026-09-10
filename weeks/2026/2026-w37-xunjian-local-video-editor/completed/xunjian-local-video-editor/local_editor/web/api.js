let token = "";
export async function request(path, data, method) {
  const options = {
    method: method || (data === undefined ? "GET" : "POST"),
    headers: {},
  };
  if (data !== undefined) {
    options.headers = {
      "Content-Type": "application/json",
      "X-Editor-Token": token,
    };
    options.body = JSON.stringify(data);
  }
  const response = await fetch(`/api${path}`, options);
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(`本機服務回傳錯誤（${response.status}），請檢查服務視窗。`);
  }
  if (!response.ok) {
    const error = new Error(
      result.error?.message ||
        result.message ||
        (typeof result.error === "string"
          ? result.error
          : `操作失敗（${response.status}）`),
    );
    error.status = response.status;
    error.code = result.error?.code || result.code;
    throw error;
  }
  return result;
}
export async function connect() {
  const session = await request("/session");
  token = session.token;
  return session;
}
export function upload(project, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(
      "POST",
      `/api/projects/${project.id}/media/upload?name=${encodeURIComponent(file.name)}&expected_version=${project.version}`,
    );
    xhr.setRequestHeader("X-Editor-Token", token);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onerror = () => reject(new Error("上傳中斷，請確認本機服務仍在執行。"));
    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 400)
          reject(
            new Error(data.error?.message || data.message || "素材匯入失敗"),
          );
        else resolve(data);
      } catch {
        reject(new Error("素材匯入回應無法讀取"));
      }
    };
    xhr.send(file);
  });
}
export function download(text, name, type = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
