// One local worker and one outstanding request; nothing is sent to a server.
export class Runtime {
  constructor(onState) {
    this.onState = onState;
    this.state = "loading_pyodide";
    this.nextId = 0;
    this.pending = null;
    this.worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
    this.ready = new Promise((resolve, reject) => {
      this.resolveReady = resolve;
      this.rejectReady = reject;
    });
    this.worker.onmessage = ({ data }) => {
      if (data.type === "state") {
        this.state = data.state;
        this.onState(data.state);
      } else if (data.type === "ready") {
        this.identity = data.identity;
        this.state = "ready";
        this.resolveReady(data.identity);
      } else if (data.type === "fatal") {
        this.fail(data.error);
      } else if (data.type === "result" && this.pending?.id === data.id) {
        const pending = this.pending;
        this.pending = null;
        this.state = "ready";
        if (data.ok) pending.resolve(data.data);
        else pending.reject(data.error);
      }
    };
    this.worker.onerror = () => this.fail({ kind: "unexpected" });
  }

  fail(error) {
    this.state = "error";
    this.onState("error");
    this.rejectReady(error);
    this.pending?.reject(error);
    this.pending = null;
  }

  call(operation, payload = {}) {
    if (this.state !== "ready" || this.pending) {
      return Promise.reject({ kind: "not_ready" });
    }
    this.state = "running";
    this.onState("running");
    return new Promise((resolve, reject) => {
      const id = ++this.nextId;
      this.pending = { id, resolve, reject };
      this.worker.postMessage({ id, operation, payload });
    });
  }
}
