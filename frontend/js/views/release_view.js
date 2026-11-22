export const releaseViewTemplate = `
<section class="panel">
  <h2>解笼拨付</h2>
  <p class="hint">
    仅核验通过的笼可拨付。写口只认笼当前票指针（乙路径命运锁）；旧票号提交即记升代偏航并拒写。
    票号留空时服务端按当前指针解析。
  </p>
  <div class="grid-2">
    <div>
      <div class="form-row">
        <div>
          <label>通过态笼</label>
          <select v-model.number="releaseForm.cage_id">
            <option :value="0">请选择</option>
            <option v-for="c in passCages" :key="c.id" :value="c.id">
              {{ c.cage_code }} · 可用 {{ fmt(c.available) }} · 代{{ c.generation }}
            </option>
          </select>
          <p class="hint" v-if="releaseForm.cage_id">
            当前票：<code>{{ (cages.find(x=>x.id===releaseForm.cage_id)||{}).current_ticket_ref || '空（拒写）' }}</code>
          </p>
        </div>
        <div>
          <label>驱动票号（空=用当前指针）</label>
          <input v-model="releaseForm.ticket_ref" placeholder="ATT-CG-XXX-001-g2"/>
        </div>
        <div>
          <label>金额（空=全额）</label>
          <input type="number" v-model.number="releaseForm.amount" min="0" step="1000" placeholder="全额"/>
        </div>
        <div>
          <label>收款方（空=受益人）</label>
          <input v-model="releaseForm.payee"/>
        </div>
      </div>
      <div class="actions">
        <button class="ok" @click="doRelease">解笼拨付</button>
      </div>
    </div>
    <div>
      <table>
        <thead>
          <tr><th>凭证</th><th>笼</th><th>驱动票号</th><th>金额</th><th>收款方</th><th>笼代</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in releases" :key="r.id">
            <td>{{ r.release_ref }}</td>
            <td>{{ r.cage_code }}</td>
            <td><code>{{ ticketOf(r.cage_id, r.cage_generation) }}</code></td>
            <td>{{ fmt(r.amount) }}</td>
            <td>{{ r.payee }}</td>
            <td>{{ r.cage_generation }}</td>
            <td>{{ r.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
`;
