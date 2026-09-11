/** 跨语言联调 fixture：只替换 Provider 输出，HTTP、Agent、Session、提交器全部真实执行。 */
import { createModels, fauxProvider, fauxAssistantMessage, fauxToolCall } from "@earendil-works/pi-ai";
import { createPiRuntimeServer } from "../src/server.js";
import { PiProviderRunExecutor } from "../src/runtime/executor.js";
const faux = fauxProvider({ provider:"cross-language-test", models:[{ id:"test-model" }] });
const models = createModels(); models.setProvider(faux.provider);
const create = [{ operation_id:"create", operation_type:"create_object", payload:{ id:"constraint-1", object_type:"constraint", title:"单机使用", type_status:"effective" } }];
const update = [{ operation_id:"update", operation_type:"update_object", payload:{ id:"constraint-1", title:"单机离线使用" } }];
faux.setResponses([
  fauxAssistantMessage(fauxToolCall("workspace_propose",{ operations:create,change_summary:"单机约束" })),fauxAssistantMessage("建议单机使用，请确认。"),
  fauxAssistantMessage(fauxToolCall("workspace_commit",{})),fauxAssistantMessage("已应用单机约束。"),
  fauxAssistantMessage(fauxToolCall("workspace_propose",{ operations:update,change_summary:"离线约束" })),fauxAssistantMessage("建议增加离线，请确认。"),
  fauxAssistantMessage(fauxToolCall("workspace_commit",{})),fauxAssistantMessage("已应用离线约束。"),
  fauxAssistantMessage(fauxToolCall("workspace_propose",{operations:[{operation_id:"handoff",operation_type:"confirm_handoff",payload:{}}],change_summary:"确认当前交接"})),fauxAssistantMessage("请确认当前交接内容与未决项。"),
  fauxAssistantMessage(fauxToolCall("workspace_commit",{})),fauxAssistantMessage("已确认交接。"),
]);
const runtime = createPiRuntimeServer({ host:"127.0.0.1",port:0,storageDir:process.argv[2],executor:new PiProviderRunExecutor({providerId:"cross-language-test",modelId:"test-model",models}) });
await runtime.listen();
const address = runtime.server.address();
process.stdout.write(JSON.stringify({port:typeof address === "object" && address ? address.port:0})+"\n");
process.on("SIGTERM",async()=>{await runtime.close();process.exit(0);});
