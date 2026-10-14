/* Menu "+" của khung gõ (0.148.0): sổ đăng ký, lọc thư mục, hàng đợi tải lên.

       node tests/js/test_menu_cong.js
*/
const fs = require("fs");
const path = require("path");
const P = require("../../dashboard/composer-plus.js");
const ROOT = path.join(__dirname, "../..");
const src = fs.readFileSync(path.join(ROOT, "dashboard/composer-plus.js"), "utf8");
const app = fs.readFileSync(path.join(ROOT, "dashboard/app.js"), "utf8");
const html = fs.readFileSync(path.join(ROOT, "dashboard/index.html"), "utf8");
let fails = [];
function check(name, cond) { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); }

const reg = P.createRegistry();
reg.register({ id: "b", order: 20, label: "x.b" });
reg.register({ id: "a", order: 10, label: "x.a" });
reg.register({ id: "b", order: 5, label: "x.b2" });
check("sổ đăng ký xếp theo order, đăng ký lại cùng id thì thay", reg.list().map(i => i.id + ":" + i.label).join(",") === "b:x.b2,a:x.a");

const f = (rel) => ({ name: rel.split("/").pop(), webkitRelativePath: rel });
let r = P.pickFolderFiles([f("du-an/a.md"), f("du-an/.env"), f("du-an/.git/config"), f("du-an/node_modules/x/i.js"), f("du-an/con/b.csv")]);
check("thư mục: bỏ file ẩn, .git, node_modules", r.files.map(x => x.name).join(",") === "a.md,b.csv" && r.skipped === 3 && r.over === 0);
const many = []; for (let i = 0; i < 61; i++) many.push(f("d/" + i + ".txt"));
r = P.pickFolderFiles(many);
check("thư mục: trần " + P.MAX_FOLDER_FILES + " file, báo số dư", r.files.length === P.MAX_FOLDER_FILES && r.over === 11);
r = P.pickFolderFiles([f("d/.DS_Store")]);
check("thư mục toàn file ẩn: không còn file nào", r.files.length === 0 && r.skipped === 1);

(async () => {
  let dang = 0, max = 0, xong = [];
  await P.runQueue([1, 2, 3, 4, 5, 6, 7, 8, 9], async (x) => {
    dang++; max = Math.max(max, dang); await new Promise(res => setTimeout(res, 5)); dang--; xong.push(x);
    if (x === 3) throw new Error("hỏng");
  }, 4);
  check("hàng đợi: tối đa 4 file cùng lúc, file hỏng không chặn file sau", max === 4 && xong.length === 9);

  ["attach", "folder", "brain_file", "commands", "connections", "partners"].forEach(id =>
    check("mục mặc định có id " + id, src.indexOf('id: "' + id + '"') !== -1));
  check("Ctrl+U chặn mặc định của trình duyệt (xem mã nguồn)", /key === "u"[\s\S]{0,400}preventDefault/.test(src));
  check("mục lệnh mở menu / bằng sự kiện input", src.indexOf('new Event("input"') !== -1);
  check("gọi trợ lý chèn đúng token của menu /", src.indexOf('"/agent-" + ') !== -1 && src.indexOf('"/workflow-" + ') !== -1);
  check("app.js lộ JavisAttach (pick, upload, addBrainFile, note)", /window\.JavisAttach = \{[\s\S]*pick[\s\S]*upload[\s\S]*addBrainFile[\s\S]*note/.test(app));
  check("composer-plus.js nạp sau model-picker.js", html.indexOf("model-picker.js") < html.indexOf("composer-plus.js"));
  check("không chữ Việt trong mã chạy của composer-plus.js",
    !/[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i.test(src.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")));
  if (fails.length) { console.log("\nFAIL - test_menu_cong: " + fails.length + " lỗi"); process.exit(1); }
  console.log("\nOK - test_menu_cong: tất cả pass");
})();
