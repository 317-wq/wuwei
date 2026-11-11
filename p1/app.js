(function () {
  "use strict";

  var MAX_SIZE = 10 * 1024 * 1024; // 10MB
  var ALLOWED_EXT = [".pdf", ".doc", ".docx"];

  var dropzone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var emptyState = document.getElementById("dropzone-empty");
  var fileState = document.getElementById("dropzone-file");
  var fileNameEl = document.getElementById("file-name");
  var fileSizeEl = document.getElementById("file-size");
  var removeBtn = document.getElementById("file-remove");
  var form = document.getElementById("upload-form");
  var status = document.getElementById("form-status");
  var prevBtn = document.getElementById("btn-prev");
  var finishBtn = document.getElementById("btn-finish");

  var currentFile = null;
  var dragDepth = 0;

  /* ---------- 工具函数 ---------- */

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function extOf(name) {
    var i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i).toLowerCase();
  }

  function setStatus(message, type) {
    status.textContent = message || "";
    status.classList.remove("is-error", "is-success");
    if (type) status.classList.add("is-" + type);
  }

  function validate(file) {
    if (!file) return "请选择一个简历文件";
    if (ALLOWED_EXT.indexOf(extOf(file.name)) === -1) {
      return "仅支持 PDF、DOC、DOCX 格式的文件";
    }
    if (file.size > MAX_SIZE) {
      return "文件不能超过 10MB";
    }
    return "";
  }

  /* ---------- 文件状态渲染 ---------- */

  function showFile(file) {
    currentFile = file;
    dropzone.classList.remove("is-invalid");
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = formatSize(file.size);
    fileNameEl.title = file.name;
    emptyState.hidden = true;
    fileState.hidden = false;
    dropzone.classList.add("has-file");
    setStatus("");
  }

  function clearFile(options) {
    var refocus = options && options.refocus;
    currentFile = null;
    input.value = "";
    emptyState.hidden = false;
    fileState.hidden = true;
    dropzone.classList.remove("has-file");
    fileNameEl.textContent = "";
    fileSizeEl.textContent = "";
    fileNameEl.removeAttribute("title");
    setStatus("");
    if (refocus) input.click();
  }

  function acceptFiles(fileList) {
    var file = fileList && fileList[0];
    var error = validate(file);
    if (error) {
      setStatus(error, "error");
      return;
    }
    showFile(file);
  }

  /* ---------- 选择文件 ---------- */

  input.addEventListener("change", function () {
    acceptFiles(input.files);
  });

  dropzone.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });

  removeBtn.addEventListener("click", function (event) {
    // 阻止 label 的默认行为，否则会同时弹出文件选择框
    event.preventDefault();
    event.stopPropagation();
    clearFile({ refocus: false });
    dropzone.focus();
  });

  /* ---------- 拖拽上传 ---------- */

  ["dragenter", "dragover"].forEach(function (type) {
    dropzone.addEventListener(type, function (event) {
      event.preventDefault();
      if (type === "dragenter") dragDepth += 1;
      dropzone.classList.add("is-dragover");
    });
  });

  dropzone.addEventListener("dragleave", function (event) {
    event.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) dropzone.classList.remove("is-dragover");
  });

  dropzone.addEventListener("drop", function (event) {
    event.preventDefault();
    dragDepth = 0;
    dropzone.classList.remove("is-dragover");

    var files = event.dataTransfer && event.dataTransfer.files;
    if (!files || !files.length) return;

    try {
      input.files = files;
    } catch (err) {
      /* 某些浏览器不允许给 input.files 赋值，退回只用本地状态 */
    }
    acceptFiles(files);
  });

  // 避免拖到页面其他位置时被浏览器直接打开
  ["dragover", "drop"].forEach(function (type) {
    document.addEventListener(type, function (event) {
      if (!dropzone.contains(event.target)) event.preventDefault();
    });
  });

  /* ---------- 提交 ---------- */

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    if (!currentFile) {
      setStatus("请先上传你的简历文件", "error");
      dropzone.classList.add("is-invalid");
      dropzone.focus();
      window.setTimeout(function () {
        dropzone.classList.remove("is-invalid");
      }, 1400);
      return;
    }

    finishBtn.disabled = true;
    finishBtn.textContent = "Uploading…";
    setStatus("正在上传 " + currentFile.name, "");

    window.setTimeout(function () {
      finishBtn.disabled = false;
      finishBtn.textContent = "Finish";
      setStatus("简历已提交，我们会尽快为你解析并优化。", "success");
    }, 900);
  });

  prevBtn.addEventListener("click", function () {
    setStatus("已返回上一步（演示，无实际跳转）", "");
  });
})();
