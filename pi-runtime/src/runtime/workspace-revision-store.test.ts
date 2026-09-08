import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { WorkspaceRevisionStore, type WorkspaceCommitRequest } from "./workspace-revision-store.js";

function request(workspace="w", key="key", id="e1"): WorkspaceCommitRequest {
  return {
    contract_type:"workspace_commit_request",schema_version:"evocanvas.pi-runtime.v1",
    tool_context:{ workspace_id:workspace,actor_id:"u",capabilities:["workspace:commit"],session_id:"s",entry_id:"e",turn_id:"t",invocation_id:"i",tool_call_id:"c",current_revision_id:"rev_0",instruction_bundle_version:"v1",active_skill_versions:[] },
    base_revision_id:"rev_0",idempotency_key:key,request_hash:"caller-hash",confirmation_refs:[],change_summary:"收录来源",
    operations:[{ operation_id:id,operation_type:"create_object",payload:{id,object_type:"evidence",title:"来源",summary:"原话"} }],
  };
}

test("事务拒绝同版本并发写入，失败不泄露部分对象",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"commit-atomic-"));
  const a=new WorkspaceRevisionStore({storageDir:dir});await a.init();
  const b=new WorkspaceRevisionStore({storageDir:dir});await b.init();
  try{
    const results=await Promise.allSettled([a.commit(request("w","a","a")),b.commit(request("w","b","b"))]);
    assert.equal(results.filter(r=>r.status==="fulfilled").length,1);
    assert.equal((results.find(r=>r.status==="rejected") as PromiseRejectedResult).reason.code,"workspace.stale_revision");
    const pointer=a.getPointers("w");
    assert.equal(Object.keys(a.getRevision("w",pointer.current_revision_id)!.objects).length,1);
    const bad=request("w","bad","bad");bad.base_revision_id=pointer.current_revision_id;
    bad.operations.push({operation_id:"invalid",operation_type:"create_object",payload:{object_type:"evidence",title:""}});
    await assert.rejects(a.commit(bad));
    assert.deepEqual(a.getPointers("w"),pointer);
  } finally {a.close();b.close();await rm(dir,{recursive:true,force:true});}
});

test("幂等跨重启、按工作区隔离，伪造相同 hash 不能覆盖内容",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"commit-retry-"));
  let store=new WorkspaceRevisionStore({storageDir:dir});await store.init();
  try{
    const original=request();const result=await store.commit(original);
    store.close();store=new WorkspaceRevisionStore({storageDir:dir});await store.init();
    assert.deepEqual(await store.commit(original),result);
    const different=request();different.operations[0].payload.title="篡改";
    await assert.rejects(store.commit(different),{code:"workspace.idempotency_conflict"});
    const another=await store.commit(request("another"));assert.notEqual(another.commit_id,result.commit_id);
    assert.equal(Object.keys(store.getRevision("another",another.new_revision_id)!.objects).length,1);
  }finally{store.close();await rm(dir,{recursive:true,force:true});}
});

test("任意确认字符串与缺失能力均不能写入稳定约束",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"commit-confirmation-"));
  const store=new WorkspaceRevisionStore({storageDir:dir});await store.init();
  try{
    const forged=request();forged.operations[0].payload.object_type="constraint";forged.confirmation_refs=["nonexistent"];
    await assert.rejects(store.commit(forged),{code:"workspace.confirmation_required"});
    const missing=request();delete (missing.tool_context as any).capabilities;
    await assert.rejects(store.commit(missing),{code:"auth.invalid_identity"});
    assert.equal(store.getPointers("w").current_revision_id,"rev_0");
  }finally{store.close();await rm(dir,{recursive:true,force:true});}
});
