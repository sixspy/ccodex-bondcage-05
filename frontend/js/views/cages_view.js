export const cagesViewTemplate = `
<section class="panel">
  <h2>入笼冻结</h2>
  <p class="hint">从当事人可用保证金划入新笼，写入笼代。冻结后须履约核验，才能解笼或罚没。</p>
  <div class="grid-2">
    <div>
      <div class="form-row">
        <div>
          <label>当事人键</label>
          <input v-model="freezeForm.party_key" list="party-list"/>
          <datalist id="party-list">
            <option v-for="b in bonds" :key="b.party_key" :value="b.party_key"/>
          </datalist>
        </div>
        <div>
          <label>合约号</label>
          <input v-model="freezeForm.contract_no"/>
        </div>
        <div>
          <label>金额</label>
          <input type="number" v-model.number="freezeForm.amount" min="1" step="1000"/>
        </div>
        <div>
          <label>受益人</label>
          <input v-model="freezeForm.beneficiary"/>
        </div>
        <div>
          <label>笼编码（可空自动）</label>
          <input v-model="freezeForm.cage_code" placeholder="CG-P-WEST-001"/>
        </div>
      </div>
      <div class="actions">
        <button @click="freezeCage">入笼冻结</button>
        <button class="secondary" @click="refresh">刷新</button>
      </div>
    </div>
    <div>
      <div class="cage-cards">
        <div
          class="cage-card"
          v-for="c in cages"
          :key="c.id"
          :class="{selected: selectedCage && selectedCage.id===c.id}"
          @click="selectCage(c)"
        >
          <div class="stamp-corner">{{ shortStatus(c.status) }}</div>
          <div class="code">{{ c.cage_code }}</div>
          <div class="amt">{{ fmt(c.available) }} / {{ fmt(c.amount) }}</div>
          <div>{{ c.contract_no }} · 代{{ c.generation }}</div>
          <div>当前票：<code>{{ c.current_ticket_ref || '未出票（待核验）' }}</code></div>
          <div>{{ c.party_key }} → {{ c.beneficiary }}</div>
        </div>
      </div>
    </div>
  </div>
  <div v-if="cageDetail">
    <h3>笼详情 · {{ cageDetail.cage.cage_code }}</h3>
    <table>
      <thead><tr><th>字段</th><th>值</th></tr></thead>
      <tbody>
        <tr><td>状态</td><td><span class="badge" :class="statusClass(cageDetail.cage.status)">{{ cageDetail.cage.status }}</span></td></tr>
        <tr><td>笼代</td><td>第 {{ cageDetail.cage.generation }} 代</td></tr>
        <tr><td>当前票指针</td><td><code>{{ cageDetail.cage.current_ticket_ref || '空（升代后待重裁）' }}</code></td></tr>
        <tr><td>可用 / 总额</td><td>{{ fmt(cageDetail.cage.available) }} / {{ fmt(cageDetail.cage.amount) }}</td></tr>
        <tr><td>核验票数（含旧代史迹）</td><td>{{ cageDetail.attestations.length }}</td></tr>
        <tr><td>拨付条数</td><td>{{ cageDetail.releases.length }}</td></tr>
        <tr><td>罚没条数</td><td>{{ cageDetail.forfeits.length }}</td></tr>
      </tbody>
    </table>
    <h3 style="margin-top:14px">笼内票册（同源）</h3>
    <table>
      <thead><tr><th>票号</th><th>代</th><th>结论</th><th>效力</th><th>核验员</th></tr></thead>
      <tbody>
        <tr v-for="a in cageDetail.attestations" :key="a.id">
          <td><code>{{ a.attest_ref }}</code></td>
          <td>{{ a.attest_gen }}</td>
          <td>{{ a.outcome }}</td>
          <td><span class="badge" :class="a.current ? 'pass' : 'done'">{{ a.current ? '当前票' : '旧代史迹·只读' }}</span></td>
          <td>{{ a.officer }}</td>
        </tr>
      </tbody>
    </table>
    <h3 style="margin-top:14px" v-if="cageDetail.generation_events && cageDetail.generation_events.length">升代事件</h3>
    <table v-if="cageDetail.generation_events && cageDetail.generation_events.length">
      <thead><tr><th>代际</th><th>旧票</th><th>理由</th><th>经办人</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="g in cageDetail.generation_events" :key="g.id">
          <td>g{{ g.from_generation }} → g{{ g.to_generation }}</td>
          <td><code>{{ g.old_ticket_ref || '—' }}</code></td>
          <td>{{ g.reason }}</td>
          <td>{{ g.officer }}</td>
          <td>{{ g.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</section>
`;
