export const forfeitViewTemplate = `
<section class="panel">
  <h2>罚没册</h2>
  <p class="hint">
    仅核验违约的笼可罚没。写口只认笼当前票指针（乙路径命运锁）；旧票号提交即记升代偏航并拒写。
    资金离开当事人账户，进入罚没册，不再回到可用余额。
  </p>
  <div class="grid-2">
    <div>
      <div class="form-row">
        <div>
          <label>违约态笼</label>
          <select v-model.number="forfeitForm.cage_id">
            <option :value="0">请选择</option>
            <option v-for="c in failCages" :key="c.id" :value="c.id">
              {{ c.cage_code }} · 可用 {{ fmt(c.available) }} · 代{{ c.generation }}
            </option>
          </select>
          <p class="hint" v-if="forfeitForm.cage_id">
            当前票：<code>{{ (cages.find(x=>x.id===forfeitForm.cage_id)||{}).current_ticket_ref || '空（拒写）' }}</code>
          </p>
        </div>
        <div>
          <label>驱动票号（空=用当前指针）</label>
          <input v-model="forfeitForm.ticket_ref" placeholder="ATT-CG-XXX-001-g2"/>
        </div>
        <div>
          <label>金额（空=全额）</label>
          <input type="number" v-model.number="forfeitForm.amount" min="0" step="1000" placeholder="全额"/>
        </div>
        <div style="grid-column:1/-1">
          <label>原因</label>
          <input v-model="forfeitForm.reason"/>
        </div>
      </div>
      <div class="actions">
        <button class="danger" @click="doForfeit">执行罚没</button>
      </div>
    </div>
    <div>
      <table>
        <thead>
          <tr><th>凭证</th><th>笼</th><th>驱动票号</th><th>金额</th><th>原因</th><th>笼代</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="f in forfeits" :key="f.id">
            <td>{{ f.forfeit_ref }}</td>
            <td>{{ f.cage_code }}</td>
            <td><code>{{ ticketOf(f.cage_id, f.cage_generation) }}</code></td>
            <td>{{ fmt(f.amount) }}</td>
            <td>{{ f.reason }}</td>
            <td>{{ f.cage_generation }}</td>
            <td>{{ f.created_at }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
`;
