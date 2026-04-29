import { useEffect, useRef, useCallback } from 'react'
import './App.css'

const INSTALL_CMD = '帮我安装 dazi skill https://raw.githubusercontent.com/wfnuser/dazi-skill/main/SKILL.md'

function useIntersectionObserver() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('visible')
          observer.unobserve(el)
        }
      },
      { threshold: 0.15 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return ref
}

function AnimatedDiv({ className, children, style }: {
  className?: string
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  const ref = useIntersectionObserver()
  return <div ref={ref} className={className} style={style}>{children}</div>
}

function Hero() {
  return (
    <section className="hero">
      <div className="floating-tags">
        <span className="float-tag">INTP 话多亚种</span>
        <span className="float-tag">数字游民</span>
        <span className="float-tag">精酿入门</span>
        <span className="float-tag">前大厂逃兵</span>
        <span className="float-tag">报复性熬夜</span>
        <span className="float-tag">在读博边缘试探</span>
      </div>
      <div className="hero-content">
        <h1 className="logo">搭子</h1>
        <p className="logo-sub">dazi &mdash; ai-native social matching</p>
        <p className="tagline">
          别滑了<br />
          让懂你的 AI 帮你找<em>对的人</em>
        </p>
        <p className="tagline-en">Stop swiping. Let your AI find your people.</p>
        <div className="cta-group">
          <a href="#install" className="cta cta-primary">Install Skill</a>
          <a href="#how" className="cta cta-secondary">How it works</a>
        </div>
      </div>
    </section>
  )
}

function ProfileCard({ nickname, tags }: { nickname: string; tags: string[] }) {
  return (
    <AnimatedDiv className="profile-card">
      <div className="profile-nickname">{nickname}</div>
      <div className="profile-tags">
        {tags.map((tag, i) => (
          <div key={i} className="profile-tag">{tag}</div>
        ))}
      </div>
    </AnimatedDiv>
  )
}

function Demo() {
  return (
    <section className="demo">
      <p className="section-label">What a match looks like</p>
      <h2 className="section-title">3 个标签，找到聊得来的人</h2>
      <div className="profile-cards">
        <ProfileCard
          nickname="微扰"
          tags={['前大厂逃兵，全职独立开发', 'INTP 社恐但话多，想多做少', '精酿、摄影、深度游，夜猫子']}
        />
        <ProfileCard
          nickname="Kira"
          tags={['ENFP 行动派，想到就冲', '产品经理转创业，做旅行社区', '徒步 + 精酿 + 猫奴']}
        />
      </div>
      <AnimatedDiv className="profile-card" style={{ maxWidth: 600, margin: '0 auto' }}>
        <div className="match-reason">
          <strong>AI 说：</strong>你们都从大厂出来自己干，都在探索新方向。她是行动派你是思考派
          &mdash; 她能推你一把，你帮她想清楚。都喜欢精酿和深度游，北京见面方便。
          <br /><br />
          <span style={{ color: 'var(--text-dim)' }}>
            &#x26A0;&#xFE0F; 她是计划狂你是随性派，旅行时可能要磨合
          </span>
        </div>
      </AnimatedDiv>
    </section>
  )
}

const STEPS = [
  {
    title: '给自己起个昵称，写 3 个标签',
    desc: '不用填表，随便写。你是什么样的人？',
    code: (
      <>
        <span className="prompt">&gt;</span> <span className="cmd">/dazi-match</span>
        <br /><br />
        <span className="comment"># Pick a nickname?</span><br />
        <span className="cmd">微扰</span><br /><br />
        <span className="comment"># 3 tags to describe yourself:</span><br />
        <span className="cmd">前大厂逃兵，全职独立开发</span><br />
        <span className="cmd">INTP 社恐但话多</span><br />
        <span className="cmd">精酿、摄影、深度游</span>
      </>
    ),
  },
  {
    title: '说一句你想找什么搭子',
    desc: '自然语言就行，AI 自己理解你的意思',
    code: (
      <>
        <span className="prompt">&gt;</span>{' '}
        <span className="cmd">找个五一去大理的搭子，能接受我社恐但会做攻略</span>
      </>
    ),
  },
  {
    title: 'AI 匹配 + 你的 agent 精排',
    desc: '服务端智能匹配，你本地的 AI 帮你挑最合适的，还会告诉你为什么推荐',
  },
  {
    title: '双向确认，交换联系方式',
    desc: '你想认识对方 + 对方也想认识你 = 匹配成功，互换微信/Telegram',
  },
]

function HowItWorks() {
  return (
    <section className="how" id="how">
      <p className="section-label">How it works</p>
      <h2 className="section-title">30 秒注册，AI 帮你找搭子</h2>
      <div className="steps">
        {STEPS.map((step, i) => (
          <AnimatedDiv key={i} className="step">
            <div className="step-num">{i + 1}</div>
            <div className="step-content">
              <h3>{step.title}</h3>
              <p>{step.desc}</p>
              {step.code && <div className="step-code">{step.code}</div>}
            </div>
          </AnimatedDiv>
        ))}
      </div>
    </section>
  )
}

function Install() {
  const handleCopy = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    navigator.clipboard.writeText(INSTALL_CMD).then(() => {
      const hint = e.currentTarget.querySelector('.copy-hint') as HTMLElement
      if (hint) {
        hint.textContent = 'copied!'
        hint.style.color = 'var(--mint)'
        setTimeout(() => {
          hint.textContent = 'click to copy'
          hint.style.color = ''
        }, 2000)
      }
    })
  }, [])

  return (
    <section className="install" id="install">
      <p className="section-label">Get started</p>
      <h2 className="section-title">安装 dazi skill</h2>
      <div className="install-box">
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Tell your AI agent:
        </p>
        <div className="install-cmd" onClick={handleCopy}>
          <span>{INSTALL_CMD}</span>
          <span className="copy-hint">click to copy</span>
        </div>
        <p className="install-or">works with</p>
        <div className="install-links">
          <a href="#" className="install-link">Claude Code</a>
          <a href="#" className="install-link">OpenClaw</a>
          <a href="#" className="install-link">Hermes</a>
        </div>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="footer">
      <p className="footer-text">
        built by{' '}
        <a href="https://www.xiaohongshu.com/user/profile/5b0d752e11be104d5db639f3">微扰</a>
        {' '}with ❤️ &middot;{' '}
        <a href="https://github.com/wfnuser/dazi-skill">source</a>
        {' '}&middot;{' '}
        agent skills standard
      </p>
    </footer>
  )
}

export default function App() {
  return (
    <>
      <Hero />
      <Demo />
      <HowItWorks />
      <Install />
      <Footer />
    </>
  )
}
