#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.room_checker import RoomChecker

def test_url_fixes():
    """测试所有平台的URL修复效果"""
    print("开始测试所有平台的URL修复效果...")
    
    # 测试用例 - 覆盖所有平台
    test_cases = [
        # 抖音
        ("https://live.douyin.com/123456/", "123456"),
        ("https://live.douyin.com/123456", "123456"),
        ("https://live.douyin.com/", None),
        ("https://live.douyin.com/yall1102/", "yall1102"),
        ("https://v.douyin.com/iQFeBnt/", None),  # 短链接
        
        # TikTok
        ("https://www.tiktok.com/@pearlgaga88/live/", "pearlgaga88"),
        ("https://www.tiktok.com/@pearlgaga88/live", "pearlgaga88"),
        ("https://www.tiktok.com/@user123", None),  # 非直播链接
        
        # 快手
        ("https://live.kuaishou.com/u/yall1102/", "yall1102"),
        ("https://live.kuaishou.com/u/yall1102", "yall1102"),
        ("https://live.kuaishou.com/u/", None),
        ("https://v.kuaishou.com/abc123", None),  # 短链接
        
        # 虎牙
        ("https://www.huya.com/52333/", "52333"),
        ("https://www.huya.com/52333", "52333"),
        ("https://www.huya.com/", None),
        ("https://m.huya.com/52333/", "52333"),
        
        # 斗鱼
        ("https://www.douyu.com/3637778/", "3637778"),
        ("https://www.douyu.com/3637778", "3637778"),
        ("https://www.douyu.com/", None),
        ("https://www.douyu.com/topic/wzDBLS6?rid=4921614", "4921614"),
        ("https://www.douyu.com/room/123456/", "123456"),
        
        # YY
        ("https://www.yy.com/22490906/22490906/", "22490906"),
        ("https://www.yy.com/22490906/22490906", "22490906"),
        ("https://www.yy.com/", None),
        
        # B站
        ("https://live.bilibili.com/320/", "320"),
        ("https://live.bilibili.com/320", "320"),
        ("https://live.bilibili.com/", None),
        ("https://live.bilibili.com/h5/320/", "320"),
        ("https://live.bilibili.com/h5/320", "320"),
        
        # 小红书
        ("https://www.xiaohongshu.com/user/profile/123456/", "123456"),
        ("https://www.xiaohongshu.com/user/profile/123456", "123456"),
        ("https://www.xiaohongshu.com/user/profile/", None),
        ("http://xhslink.com/xpJpfM", None),  # 短链接
        
        # Bigo
        ("https://www.bigo.tv/cn/716418802/", "716418802"),
        ("https://www.bigo.tv/cn/716418802", "716418802"),
        ("https://www.bigo.tv/cn/", None),
        ("https://www.bigo.tv/716418802/", "716418802"),
        
        # Blued
        ("https://app.blued.cn/live?id=Mp6G2R", "Mp6G2R"),
        ("https://app.blued.cn/live?id=Mp6G2R&param=value", "Mp6G2R"),
        ("https://app.blued.cn/live", None),
        
        # SOOP
        ("https://play.sooplive.co.kr/sw7love/", "sw7love"),
        ("https://play.sooplive.co.kr/sw7love", "sw7love"),
        ("https://play.sooplive.co.kr/", None),
        
        # 网易CC
        ("https://cc.163.com/583946984/", "583946984"),
        ("https://cc.163.com/583946984", "583946984"),
        ("https://cc.163.com/", None),
        
        # 千度热播
        ("https://qiandurebo.com/web/video.php?roomnumber=33333", "33333"),
        ("https://qiandurebo.com/web/video.php?roomnumber=33333&param=value", "33333"),
        ("https://qiandurebo.com/web/video.php", None),
        
        # PandaTV
        ("https://www.pandalive.co.kr/live/play/bara0109/", "bara0109"),
        ("https://www.pandalive.co.kr/live/play/bara0109", "bara0109"),
        ("https://www.pandalive.co.kr/live/play/", None),
        
        # 猫耳FM
        ("https://fm.missevan.com/live/868895007/", "868895007"),
        ("https://fm.missevan.com/live/868895007", "868895007"),
        ("https://fm.missevan.com/live/", None),
        
        # Look直播
        ("https://look.163.com/live?id=65108820", "65108820"),
        ("https://look.163.com/live?id=65108820&position=3", "65108820"),
        ("https://look.163.com/live", None),
        
        # WinkTV
        ("https://www.winktv.co.kr/live/play/anjer1004/", "anjer1004"),
        ("https://www.winktv.co.kr/live/play/anjer1004", "anjer1004"),
        ("https://www.winktv.co.kr/live/play/", None),
        
        # FlexTV
        ("https://www.flextv.co.kr/channels/593127/live/", "593127"),
        ("https://www.flextv.co.kr/channels/593127/live", "593127"),
        ("https://www.flextv.co.kr/channels/", None),
        
        # PopkonTV
        ("https://www.popkontv.com/live/view?castId=wjfal007", "wjfal007"),
        ("https://www.popkontv.com/live/view?castId=wjfal007&partnerCode=P-00117", "wjfal007"),
        ("https://www.popkontv.com/channel/notices?mcid=wjfal007", "wjfal007"),
        ("https://www.popkontv.com/live/view", None),
        
        # TwitCasting
        ("https://twitcasting.tv/c:uonq/", "uonq"),
        ("https://twitcasting.tv/c:uonq", "uonq"),
        ("https://twitcasting.tv/", None),
        
        # 百度直播
        ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377", "9175031377"),
        ("https://live.baidu.com/m/media/pclive/pchome/live.html?room_id=9175031377&tab_category", "9175031377"),
        ("https://live.baidu.com/m/media/pclive/pchome/live.html", None),
        
        # 微博直播
        ("https://weibo.com/l/wblive/p/show/1022:2321325026370190442592", "2321325026370190442592"),
        ("https://weibo.com/l/wblive/p/show/1022:123456", "123456"),
        ("https://weibo.com/l/wblive/p/show/", None),
        
        # 酷狗直播
        ("https://fanxing2.kugou.com/50428671/", "50428671"),
        ("https://fanxing2.kugou.com/50428671", "50428671"),
        ("https://fanxing2.kugou.com/", None),
        ("https://fanxing2.kugou.com/50428671?refer=2177", "50428671"),
        
        # Twitch
        ("https://www.twitch.tv/gamerbee/", "gamerbee"),
        ("https://www.twitch.tv/gamerbee", "gamerbee"),
        ("https://www.twitch.tv/", None),
        
        # LiveMe
        ("https://www.liveme.com/zh/v/17141543493018047815/", "17141543493018047815"),
        ("https://www.liveme.com/zh/v/17141543493018047815", "17141543493018047815"),
        ("https://www.liveme.com/zh/v/", None),
        
        # 花椒直播
        ("https://www.huajiao.com/l/345096174/", "345096174"),
        ("https://www.huajiao.com/l/345096174", "345096174"),
        ("https://www.huajiao.com/l/", None),
        
        # ShowRoom
        ("https://www.showroom-live.com/room/profile?room_id=480206", "480206"),
        ("https://www.showroom-live.com/room/profile?room_id=480206&param=value", "480206"),
        ("https://www.showroom-live.com/room/profile", None),
        
        # Acfun
        ("https://live.acfun.cn/live/179922/", "179922"),
        ("https://live.acfun.cn/live/179922", "179922"),
        ("https://live.acfun.cn/live/", None),
        
        # 映客直播
        ("https://www.inke.cn/liveroom/index.html?uid=22954469&id=1720860391070904", "1720860391070904"),
        ("https://www.inke.cn/liveroom/index.html?uid=123456&id=789012", "789012"),
        ("https://www.inke.cn/liveroom/index.html?uid=123456", "123456"),
        ("https://www.inke.cn/liveroom/index.html", None),
        
        # 音播直播
        ("https://live.ybw1666.com/800002949/", "800002949"),
        ("https://live.ybw1666.com/800002949", "800002949"),
        ("https://live.ybw1666.com/", None),
        
        # 知乎直播
        ("https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9/", "ac3a467005c5d20381a82230101308e9"),
        ("https://www.zhihu.com/people/ac3a467005c5d20381a82230101308e9", "ac3a467005c5d20381a82230101308e9"),
        ("https://www.zhihu.com/people/", None),
        
        # CHZZK
        ("https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2/", "458f6ec20b034f49e0fc6d03921646d2"),
        ("https://chzzk.naver.com/live/458f6ec20b034f49e0fc6d03921646d2", "458f6ec20b034f49e0fc6d03921646d2"),
        ("https://chzzk.naver.com/live/", None),
        
        # 嗨秀直播
        ("https://www.haixiutv.com/6095106/", "6095106"),
        ("https://www.haixiutv.com/6095106", "6095106"),
        ("https://www.haixiutv.com/", None),
        
        # VV星球直播
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?roomId=LP115924473", "LP115924473"),
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html?roomId=LP115924473&platformId=vvstar", "LP115924473"),
        ("https://h5webcdn-pro.vvxqiu.com//activity/videoShare/videoShare.html", None),
        
        # 17Live
        ("https://17.live/en/live/6302408/", "6302408"),
        ("https://17.live/en/live/6302408", "6302408"),
        ("https://17.live/en/live/", None),
        
        # 浪Live
        ("https://www.lang.live/en-US/room/3349463/", "3349463"),
        ("https://www.lang.live/en-US/room/3349463", "3349463"),
        ("https://www.lang.live/en-US/room/", None),
        
        # 畅聊直播
        ("https://live.tlclw.com/106188/", "106188"),
        ("https://live.tlclw.com/106188", "106188"),
        ("https://live.tlclw.com/", None),
        
        # 飘飘直播
        ("https://m.pp.weimipopo.com/live/preview.html?anchorUid=91625862", "91625862"),
        ("https://m.pp.weimipopo.com/live/preview.html?uid=91648673&anchorUid=91625862&app=plpl", "91625862"),
        ("https://m.pp.weimipopo.com/live/preview.html", None),
        
        # 六间房直播
        ("https://v.6.cn/634435/", "634435"),
        ("https://v.6.cn/634435", "634435"),
        ("https://v.6.cn/", None),
        
        # 乐嗨直播
        ("https://www.lehaitv.com/8059096/", "8059096"),
        ("https://www.lehaitv.com/8059096", "8059096"),
        ("https://www.lehaitv.com/", None),
        
        # 花猫直播
        ("https://h.catshow168.com/live/preview.html?anchorUid=18895331", "18895331"),
        ("https://h.catshow168.com/live/preview.html?uid=19066357&anchorUid=18895331", "18895331"),
        ("https://h.catshow168.com/live/preview.html", None),
        
        # Shopee
        ("https://sg.shp.ee/GmpXeuf?uid=1006401066", "1006401066"),
        ("https://sg.shp.ee/GmpXeuf?uid=1006401066&session=802458", "1006401066"),
        ("https://sg.shp.ee/GmpXeuf", None),
        
        # Youtube
        ("https://www.youtube.com/watch?v=cS6zS5hi1w0", "cS6zS5hi1w0"),
        ("https://www.youtube.com/watch?v=cS6zS5hi1w0&param=value", "cS6zS5hi1w0"),
        ("https://www.youtube.com/watch", None),
        
        # 淘宝
        ("https://m.tb.cn/h.TWp0HTd", None),  # 短链接
        ("https://item.taobao.com/item.htm?id=123456", None),  # 商品链接
        
        # 京东
        ("https://3.cn/28MLBy-E", None),  # 短链接
        ("https://item.jd.com/123456.html", None),  # 商品链接
        
        # Faceit
        ("https://www.faceit.com/zh/players/Compl1/stream/", "Compl1"),
        ("https://www.faceit.com/zh/players/Compl1/stream", "Compl1"),
        ("https://www.faceit.com/zh/players/", None),
        
        # 边界情况和错误处理
        ("", None),  # 空字符串
        ("invalid_url", None),  # 无效URL
        ("https://unknown.com/123", None),  # 未知平台
    ]
    
    success_count = 0
    total_count = len(test_cases)
    platform_results = {}
    
    print(f"总共测试 {total_count} 个URL...")
    print("=" * 80)
    
    for i, (url, expected) in enumerate(test_cases, 1):
        # 获取平台名称
        if url:
            try:
                platform = url.split("//")[1].split(".")[1] if "." in url else "unknown"
            except (IndexError, AttributeError):
                platform = "unknown"
        else:
            platform = "empty"
            
        if platform not in platform_results:
            platform_results[platform] = {"total": 0, "success": 0}
        
        result = RoomChecker.extract_room_id(url)
        is_success = result == expected
        if is_success:
            success_count += 1
            platform_results[platform]["success"] += 1
            print(f"✅ [{i:3d}] {url} -> {result}")
        else:
            print(f"❌ [{i:3d}] {url} -> {result} (期望: {expected})")
        platform_results[platform]["total"] += 1
    
    print("=" * 80)
    print(f"测试结果: {success_count}/{total_count} 通过")
    print(f"通过率: {(success_count/total_count)*100:.2f}%")
    
    print("\n各平台测试结果:")
    for platform, stats in sorted(platform_results.items()):
        success_rate = (stats["success"] / stats["total"]) * 100
        print(f"  {platform:15s}: {stats['success']:2d}/{stats['total']:2d} 通过 ({success_rate:5.2f}%)")
    
    return success_count == total_count

if __name__ == "__main__":
    success = test_url_fixes()
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 有测试失败！")
        sys.exit(1) 