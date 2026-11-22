export const auditViewTemplate = `
<section class="panel">
  <h2>审计争用</h2>
  <p class="hint">
    写动作落审计；后到争用只记 contention，不写业务。
    命运锁（{{ fate ? fate.locked_date : '' }} 当日锁死）：{{ fate ? fate.path_name : '加载中' }} —— {{ fate ? fate.rule : '' }}
  </p>
  <div class="grid-2">
    <div>
      <h3>审计</h3>
      <table>
        <thead><tr><th>时间</th><th>人</th><th>动作</th><th>目标</th><th>载荷</th></tr></thead>
        <tbody>
          <tr v-for="a in audits" :key="a.id" :class="{ 'deviation-row': a.action==='generation_deviation' }">
            <td>{{ a.created_at }}</td>
            <td>{{ a.actor }}</td>
            <td>
              <span class="badge" :class="a.action==='generation_deviation' ? 'fail' : (a.action==='generation_upgrade' ? 'pass' : 'done')">
                {{ a.action }}
              </span>
            </td>
            <td>{{ a.target }}</td>
            <td><code style="font-size:11px">{{ a.payload }}</code></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div>
      <h3>升代事件（与核验页同源）</h3>
      <table>
        <thead><tr><th>时间</th><th>笼</th><th>代际</th><th>旧票</th><th>理由</th><th>人</th></tr></thead>
        <tbody>
          <tr v-for="g in generationEvents" :key="g.id">
            <td>{{ g.created_at }}</td>
            <td>{{ g.cage_code }}</td>
            <td>g{{ g.from_generation }} → g{{ g.to_generation }}</td>
            <td><code>{{ g.old_ticket_ref || '—' }}</code></td>
            <td>{{ g.reason }}</td>
            <td>{{ g.officer }}</td>
          </tr>
          <tr v-if="!generationEvents.length"><td colspan="6" class="hint">暂无升代</td></tr>
        </tbody>
      </table>
      <h3 style="margin-top:14px">持锁</h3>
      <table>
        <thead><tr><th>键</th><th>持有者</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="l in locks" :key="l.lock_key">
            <td>{{ l.lock_key }}</td>
            <td>{{ l.holder }}</td>
            <td>{{ l.acquired_at }}</td>
          </tr>
        </tbody>
      </table>
      <h3 style="margin-top:14px">争用</h3>
      <table>
        <thead><tr><th>时间</th><th>键</th><th>人</th><th>动作</th><th>详情</th></tr></thead>
        <tbody>
          <tr v-for="c in contention" :key="c.id">
            <td>{{ c.created_at }}</td>
            <td>{{ c.lock_key }}</td>
            <td>{{ c.actor }}</td>
            <td>{{ c.action }}</td>
            <td>{{ c.detail }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</section>
`;
