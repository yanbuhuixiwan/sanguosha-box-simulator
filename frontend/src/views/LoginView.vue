<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '../composables/useToast'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()
const { error: toastError, success: toastSuccess } = useToast()

const mode = ref('login')
const username = ref('')
const password = ref('')
const nickname = ref('')
const submitting = ref(false)

function switchMode(next) {
  mode.value = next
}

async function submit() {
  if (!username.value.trim() || !password.value) {
    toastError('用户名和密码总得填一下吧')
    return
  }
  submitting.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value.trim(), password.value)
    } else {
      await auth.register(username.value.trim(), password.value, nickname.value.trim() || undefined)
      toastSuccess('注册成功，元宝已经塞进你口袋')
    }
    router.replace(route.query.redirect || '/')
  } catch (err) {
    toastError(err.message)
  } finally {
    submitting.value = false
  }
}

async function guest() {
  submitting.value = true
  const name = `guest_${Math.random().toString(36).slice(2, 8)}`
  try {
    await auth.register(name, 'guest1234', '无名杀友')
    toastSuccess('游客账号已就绪')
    router.replace('/')
  } catch (err) {
    toastError(err.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-page__bg">
      <span class="v-text login-page__poem">大梦谁先觉 平生我自知</span>
    </div>

    <div class="login-wrap">
      <section class="login-hero">
        <div class="login-hero__seal">杀</div>
        <h1>
          三国杀<br />
          <span>盒子模拟器</span>
        </h1>
        <p class="login-hero__lead">
          按官方公示权重还原半价盒与正常盒的开盒概率，另附武将招募、皮肤抽取。
          此处无真实充值，只有无穷的「就差一点」。
        </p>

        <ul class="login-hero__points">
          <li><b>权重直译</b>概率由权重表计算，不做任何暗改</li>
          <li><b>50 连上限</b>一次性开满，爽感与心痛齐飞</li>
          <li><b>战绩留痕</b>每次抽取入库，方便复盘你的非酋人生</li>
        </ul>

        <p class="login-hero__note">
          仅供娱乐与概率演示，与官方无关，不可兑换任何真实物品。
        </p>
      </section>

      <section class="login-card panel panel--pad">
        <div class="login-tabs">
          <button
            class="login-tab"
            :class="{ active: mode === 'login' }"
            @click="switchMode('login')"
          >
            登录
          </button>
          <button
            class="login-tab"
            :class="{ active: mode === 'register' }"
            @click="switchMode('register')"
          >
            注册
          </button>
        </div>

        <form class="login-form" @submit.prevent="submit">
          <div class="field">
            <label>账号</label>
            <input v-model="username" class="input" placeholder="2-20 位，中文/字母/数字" autocomplete="username" />
          </div>

          <div v-if="mode === 'register'" class="field">
            <label>昵称（可选）</label>
            <input v-model="nickname" class="input" placeholder="大厅里显示的名字" maxlength="16" />
          </div>

          <div class="field">
            <label>密码</label>
            <input
              v-model="password"
              class="input"
              type="password"
              placeholder="至少 4 位"
              autocomplete="current-password"
            />
          </div>

          <button class="btn btn-primary btn-block" type="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner" />
            {{ submitting ? '处理中' : mode === 'login' ? '进入大厅' : '创建账号' }}
          </button>

          <button type="button" class="btn btn-ghost btn-block" :disabled="submitting" @click="guest">
            一键游客试玩
          </button>
        </form>

        <p class="login-card__foot subtle">注册即送 8,888 元宝，够你把非酋底色验个明白。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 3rem 1.2rem;
  position: relative;
  overflow: hidden;
}
.login-page__bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.login-page__poem {
  position: absolute;
  right: max(1.5rem, 4vw);
  top: 12%;
  font-size: 1.5rem;
  line-height: 3.2;
}

.login-wrap {
  position: relative;
  width: min(1000px, 100%);
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: clamp(1.5rem, 4vw, 4rem);
  align-items: center;
}

.login-hero__seal {
  width: 62px;
  height: 62px;
  display: grid;
  place-items: center;
  border-radius: 2px;
  background: linear-gradient(150deg, #c02c36, #7d1a21);
  color: #f6e7cc;
  font-family: var(--font-brush);
  font-size: 2.1rem;
  box-shadow: inset 0 0 0 1px rgba(246, 231, 204, 0.42), inset 0 0 20px rgba(0, 0, 0, 0.5);
  animation: sealIn 0.8s cubic-bezier(0.2, 0.9, 0.3, 1) both;
}

.login-hero h1 {
  margin: 1.35rem 0 0;
  font-size: clamp(2.1rem, 5vw, 3.1rem);
  line-height: 1.22;
  letter-spacing: 0.1em;
  color: var(--paper);
}
.login-hero h1 span {
  color: var(--gold-2);
  position: relative;
}

.login-hero__lead {
  margin: 1.2rem 0 1.6rem;
  color: var(--paper-dim);
  line-height: 1.9;
  font-size: 0.94rem;
  max-width: 34em;
}

.login-hero__points {
  list-style: none;
  padding: 0;
  margin: 0 0 1.6rem;
  display: grid;
  gap: 0.7rem;
}
.login-hero__points li {
  display: flex;
  gap: 0.7rem;
  font-size: 0.86rem;
  color: var(--paper-mute);
  line-height: 1.7;
}
.login-hero__points b {
  flex: none;
  color: var(--gold);
  font-family: var(--font-serif);
  letter-spacing: 0.08em;
  border: 1px solid rgba(166, 124, 78, 0.3);
  border-radius: 3px;
  padding: 0 5px;
  font-size: 0.78rem;
  height: fit-content;
}

.login-hero__note {
  font-size: 0.72rem;
  color: #6f6555;
  letter-spacing: 0.05em;
  margin: 0;
}

.login-card {
  backdrop-filter: blur(6px);
}

.login-tabs {
  display: flex;
  gap: 0.4rem;
  padding: 0.3rem;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(166, 124, 78, 0.14);
  margin-bottom: 1.4rem;
}
.login-tab {
  flex: 1;
  padding: 0.5rem;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--paper-mute);
  font-family: var(--font-serif);
  letter-spacing: 0.18em;
  font-size: 0.9rem;
  cursor: pointer;
  transition: 0.22s;
}
.login-tab.active {
  background: linear-gradient(160deg, rgba(179, 38, 47, 0.9), rgba(125, 26, 33, 0.9));
  color: #fff3d8;
  box-shadow: 0 6px 18px -10px rgba(179, 38, 47, 0.9);
}

.login-form {
  display: grid;
  gap: 1rem;
}

.login-card__foot {
  text-align: center;
  margin: 1.15rem 0 0;
  font-size: 0.74rem;
}

@media (max-width: 860px) {
  .login-wrap { grid-template-columns: 1fr; }
  .login-page__poem { display: none; }
  .login-hero h1 { font-size: 2rem; }
}
</style>
