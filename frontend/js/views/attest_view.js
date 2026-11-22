export const attestViewTemplate = `
<section class="panel">
  <h2>履约核验</h2>
  <p class="hint">
    对已冻结笼给出通过或违约结论；同一笼代不得改口。通过后可解笼，违约后可罚没。
    每张票号 <code>ATT-笼号-g代</code> 唯一；命运锁：{{ fate ? fate.path_name : '加载中' }}（{{ fate ? fate.locked_date : '' }} 锁死）。
  </p>
  <div class="grid-2">
    <div>
      <div class="form-row">
        <div>
          <label>笼</label>
          <select v-model.number="attestForm.cage_id">
            <option :value="0">请选择</option>
            <option v-for="c in frozenCages" :key="c.id" :value="c.id">
              {{ c.cage_code }} · {{ fmt(c.available) }} · 代{{ c.generation }}
            </option>
          </select>
        </div>
        <div>
          <label>结论</label>
          <select v-model="attestForm.outcome">
            <option>通过</option>
            <option>违约</option>
          </select>
        </div>
        <div style="grid-column:1/-1">
          <label>证据摘要</label>
          <textarea v-model="attestForm.evidence" placeholder="验收单号 / 违约说明"></textarea>
        </div>
      </div>
      <div class="actions">
        <button class="ok" @click="doAttest">提交核验（落新票并切当前指针）</button>
      </div>

      <h3 style="margin-top:18px">核验升代（新材料重裁）</h3>
      <p class="hint">升代后笼代 +1、当前票指针置空；旧票留史只读，解笼/罚没只认新票。本代已出金则拒升。</p>
      <div class="form-row">
        <div>
          <label>已核验待重裁的笼</label>
          <select v-model.number="upgradeForm.cage_id">
            <option :value="0">请选择</option>
            <option v-for="c in cages.filter(x=>['核验通过','核验违约'].includes(x.status))" :key="c.id" :value="c.id">
              {{ c.cage_code }} · 代{{ c.generation }} · 当前票 {{ c.current_ticket_ref || '空' }}
            </option>
          </select>
        </div>
        <div style="grid-column:1/-1">
          <label>升代理由（新材料说明）</label>
          <input v-model="upgradeForm.reason"/>
        </div>
      </div>
      <div class="actions">
        <button class="danger" @click="doUpgradeGeneration">申请核验升代</button>
      </div>
    </div>
    <div>
      <table>
        <thead>
          <tr><th>时间</th><th>笼</th><th>票号</th><th>结论</th><th>笼代</th><th>效力</th><th>核验员</th><th>证据</th></tr>
        </thead>
        <tbody>
          <tr v-for="a in attestations" :key="a.id">
            <td>{{ a.created_at }}</td>
            <td>{{ a.cage_code }}</td>
            <td><code>{{ a.attest_ref }}</code></td>
            <td><span class="badge" :class="a.outcome==='通过'?'pass':'fail'">{{ a.outcome }}</span></td>
            <td>{{ a.attest_gen }}</td>
            <td>
              <span class="badge" :class="a.current ? 'pass' : 'done'">
                {{ a.current ? '当前票' : '旧代史迹·只读' }}
              </span>
            </td>
            <td>{{ a.officer }}</td>
            <td>{{ a.evidence }}</td>
          </tr>
        </tbody>
      </table>
      <h3 style="margin-top:14px">升代事件</h3>
      <table>
        <thead>
          <tr><th>时间</th><th>笼</th><th>代际</th><th>旧票</th><th>理由</th><th>经办人</th></tr>
        </thead>
        <tbody>
          <tr v-for="g in generationEvents" :key="g.id">
            <td>{{ g.created_at }}</td>
            <td>{{ g.cage_code }}</td>
            <td>g{{ g.from_generation }} → g{{ g.to_generation }}</td>
            <td><code>{{ g.old_ticket_ref || '—' }}</code></td>
            <td>{{ g.reason }}</td>
            <td>{{ g.officer }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
`;
