# -*- coding: utf8 -*-
import datetime
import json
import time

from www.db import BaseConnection
from www.models import TenantServiceInfo, TenantServiceInfoDelete, \
    TenantServiceRelation, TenantServiceAuth, TenantServiceEnvVar, \
    TenantRegionInfo, TenantServicesPort, TenantServiceMountRelation, \
    TenantServiceEnv, ServiceDomain, Tenants, AppService, Users, \
    AppServicePort, AppServiceEnv, AppServiceVolume, TenantServiceVolume, \
    ServiceInfo, ServiceExtendMethod, AppServiceRelation
from www.service_http import RegionServiceApi
from www.app_http import AppServiceApi
from www.region import RegionInfo
from www.utils import sn
from django.conf import settings
from www.monitorservice.monitorhook import MonitorHook
from www.tenantservice.baseservice import TenantRegionService

import logging
logger = logging.getLogger('default')

monitorhook = MonitorHook()
regionClient = RegionServiceApi()
tenantRegionService = TenantRegionService()
appClient = AppServiceApi()


class OpenTenantServiceManager(object):

    def __init__(self):
        self.feerule = settings.REGION_RULE
        self.MODULES = settings.MODULES

    def prepare_mapping_port(self, service, container_port):
        port_list = TenantServicesPort.objects.filter(tenant_id=service.tenant_id, mapping_port__gt=container_port).values_list(
            'mapping_port', flat=True).order_by('mapping_port')

        port_list = list(port_list)
        port_list.insert(0, container_port)
        max_port = reduce(lambda x, y: y if (y - x) == 1 else x, port_list)
        return max_port + 1

    def create_service(self, service_id, tenant_id, service_alias, service, creater, region, service_origin='assistant'):
        """创建console服务"""
        tenantServiceInfo = {}
        tenantServiceInfo["service_id"] = service_id
        tenantServiceInfo["tenant_id"] = tenant_id
        tenantServiceInfo["service_key"] = service.service_key
        tenantServiceInfo["service_alias"] = service_alias
        tenantServiceInfo["service_region"] = region
        tenantServiceInfo["desc"] = service.desc
        tenantServiceInfo["category"] = service.category
        tenantServiceInfo["image"] = service.image
        tenantServiceInfo["cmd"] = service.cmd
        tenantServiceInfo["setting"] = service.setting
        tenantServiceInfo["extend_method"] = service.extend_method
        tenantServiceInfo["env"] = service.env
        tenantServiceInfo["min_node"] = service.min_node
        tenantServiceInfo["min_cpu"] = service.min_cpu
        tenantServiceInfo["min_memory"] = service.min_memory
        tenantServiceInfo["inner_port"] = service.inner_port
        tenantServiceInfo["version"] = service.version
        tenantServiceInfo["namespace"] = service.namespace
        tenantServiceInfo["update_version"] = service.update_version
        volume_path = ""
        host_path = ""
        if bool(service.volume_mount_path):
            volume_path = service.volume_mount_path
            host_path = "/grdata/tenant/" + tenant_id + "/service/" + service_id
        tenantServiceInfo["volume_mount_path"] = volume_path
        tenantServiceInfo["host_path"] = host_path
        if service.service_key == 'application':
            tenantServiceInfo["deploy_version"] = ""
        else:
            tenantServiceInfo["deploy_version"] = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        tenantServiceInfo["create_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tenantServiceInfo["git_project_id"] = 0
        tenantServiceInfo["service_type"] = service.service_type
        tenantServiceInfo["creater"] = creater
        tenantServiceInfo["total_memory"] = service.min_node * service.min_memory
        tenantServiceInfo["service_origin"] = service_origin
        newTenantService = TenantServiceInfo(**tenantServiceInfo)
        newTenantService.save()
        return newTenantService

    def create_region_service(self, newTenantService, domain, region, nick_name, do_deploy=True):
        """创建region服务"""
        data = {}
        data["tenant_id"] = newTenantService.tenant_id
        data["service_id"] = newTenantService.service_id
        data["service_key"] = newTenantService.service_key
        data["comment"] = newTenantService.desc
        data["image_name"] = newTenantService.image
        data["container_cpu"] = newTenantService.min_cpu
        data["container_memory"] = newTenantService.min_memory
        data["volume_path"] = "vol" + newTenantService.service_id[0:10]
        data["volume_mount_path"] = newTenantService.volume_mount_path
        data["host_path"] = newTenantService.host_path
        data["extend_method"] = newTenantService.extend_method
        data["status"] = 0
        data["replicas"] = newTenantService.min_node
        data["service_alias"] = newTenantService.service_alias
        data["service_version"] = newTenantService.version
        data["container_env"] = newTenantService.env
        data["container_cmd"] = newTenantService.cmd
        data["node_label"] = ""
        data["deploy_version"] = newTenantService.deploy_version if do_deploy else None
        data["domain"] = domain
        data["category"] = newTenantService.category
        data["operator"] = nick_name
        data["service_type"] = newTenantService.service_type
        data["extend_info"] = {"ports": [], "envs": []}
        data["namespace"] = newTenantService.namespace
        if hasattr(newTenantService, "service_origin"):
            data["service_origin"] = newTenantService.service_origin

        ports_info = TenantServicesPort.objects.filter(service_id=newTenantService.service_id).values(
            'container_port', 'mapping_port', 'protocol', 'port_alias', 'is_inner_service', 'is_outer_service')
        if ports_info:
            data["extend_info"]["ports"] = list(ports_info)
    
        envs_info = TenantServiceEnvVar.objects.filter(service_id=newTenantService.service_id).values(
            'container_port', 'name', 'attr_name', 'attr_value', 'is_change', 'scope')
        if envs_info:
            data["extend_info"]["envs"] = list(envs_info)

        volume_info = TenantServiceVolume.objects.filter(service_id=newTenantService.service_id).values(
            'service_id', 'category', 'host_path', 'volume_path')
        if volume_info:
            data["extend_info"]["volume"] = list(volume_info)

        logger.debug(newTenantService.tenant_id + " start create_service:" + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
        regionClient.create_service(region, newTenantService.tenant_id, json.dumps(data))
        logger.debug(newTenantService.tenant_id + " end create_service:" + datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    
    def delete_service(self, tenant, service, username):
        try:
            # 检查服务关联
            published = AppService.objects.filter(service_id=service.service_id).count()
            if published:
                logger.debug("openapi.services", "services has related published!".format(tenant.tenant_name, service.service_name))
                return 409, False, u"关联了已发布服务, 不可删除"
            # 检查服务依赖
            dep_service_ids = TenantServiceRelation.objects.filter(dep_service_id=service.service_id).values("service_id")
            if len(dep_service_ids) > 0:
                sids = []
                for ds in dep_service_ids:
                    sids.append(ds["service_id"])
                if len(sids) > 0:
                    alias_list = TenantServiceInfo.objects.filter(service_id__in=sids).values('service_alias')
                    dep_alias = ""
                    for alias in alias_list:
                        if dep_alias != "":
                            dep_alias += ","
                        dep_alias = dep_alias + alias["service_alias"]
                    logger.debug("openapi.services", "{0} depended current services, cannot delete!".format(dep_alias))
                    return 410, False, u"{0} 依赖当前服务,不可删除".format(dep_alias)
            # 检查挂载依赖
            dep_service_ids = TenantServiceMountRelation.objects.filter(dep_service_id=service.service_id).values("service_id")
            if len(dep_service_ids) > 0:
                sids = []
                for ds in dep_service_ids:
                    sids.append(ds["service_id"])
                if len(sids) > 0:
                    alias_list = TenantServiceInfo.objects.filter(service_id__in=sids).values('service_alias')
                    dep_alias = ""
                    for alias in alias_list:
                        if dep_alias != "":
                            dep_alias += ","
                        dep_alias = dep_alias + alias["service_alias"]
                    logger.debug("openapi.services", "{0} mnt depended current services, cannot delete!".format(dep_alias))
                    return 411, False, u"{0} 挂载依赖当前服务,不可删除".format(dep_alias)
            # 删除服务
            # 备份删除数据
            data = service.toJSON()
            tenant_service_info_delete = TenantServiceInfoDelete(**data)
            tenant_service_info_delete.save()
            # 删除region服务
            try:
                regionClient.delete(service.service_region, service.service_id)
            except Exception as e:
                logger.exception("openapi.services", e)
            # 删除console服务
            TenantServiceInfo.objects.get(service_id=service.service_id).delete()
            # env/auth/domain/relationship/envVar delete
            TenantServiceEnv.objects.filter(service_id=service.service_id).delete()
            TenantServiceAuth.objects.filter(service_id=service.service_id).delete()
            ServiceDomain.objects.filter(service_id=service.service_id).delete()
            TenantServiceRelation.objects.filter(service_id=service.service_id).delete()
            TenantServiceEnvVar.objects.filter(service_id=service.service_id).delete()
            TenantServiceMountRelation.objects.filter(service_id=service.service_id).delete()
            TenantServicesPort.objects.filter(service_id=service.service_id).delete()
            TenantServiceVolume.objects.filter(service_id=service.service_id).delete()
            monitorhook.serviceMonitor(username, service, 'app_delete', True)
            logger.debug("openapi.services", "delete service.result:success")
            return 200, True, u"删除成功"
        except Exception as e:
            logger.exception("openapi.services", e)
            logger.debug("openapi.services", "delete service.result:failure")
            return 412, False, u"删除失败"

    def remove_service(self, tenant, service, username):
        try:
            # 检查当前服务的依赖服务
            dep_service_relation = TenantServiceRelation.objects.filter(service_id=service.service_id)
            if len(dep_service_relation) > 0:
                dep_service_ids = [x.dep_service_id for x in list(dep_service_relation)]
                logger.debug(dep_service_ids)
                # 删除依赖服务
                dep_service_list = TenantServiceInfo.objects.filter(service_id__in=list(dep_service_ids))
                for dep_service in list(dep_service_list):
                    try:
                        regionClient.delete(dep_service.service_region, dep_service.service_id)
                        TenantServiceInfo.objects.filter(pk=dep_service.ID).delete()
                        TenantServiceEnv.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServiceAuth.objects.filter(service_id=dep_service.service_id).delete()
                        ServiceDomain.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServiceRelation.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServiceEnvVar.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServiceMountRelation.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServicesPort.objects.filter(service_id=dep_service.service_id).delete()
                        TenantServiceVolume.objects.filter(service_id=dep_service.service_id).delete()
                        monitorhook.serviceMonitor(username, dep_service, 'app_delete', True)
                    except Exception as e:
                        logger.exception("openapi.services", e)
            logger.debug("openapi.services", "dep service delete!")
            # 删除挂载关系
            TenantServiceMountRelation.objects.filter(service_id=service.service_id).delete()
            # 删除被挂载关系
            TenantServiceMountRelation.objects.filter(dep_service_id=service.service_id).delete()
            logger.debug("openapi.services", "dep mnt delete!")
            data = service.toJSON()
            tenant_service_info_delete = TenantServiceInfoDelete(**data)
            tenant_service_info_delete.save()
            logger.debug("openapi.services", "add delete record!")
            # 删除region服务
            try:
                regionClient.delete(service.service_region, service.service_id)
            except Exception as e:
                logger.exception("openapi.services", e)
            logger.debug("openapi.services", "delete region service!")
            # 删除console服务
            TenantServiceInfo.objects.filter(service_id=service.service_id).delete()
            # env/auth/domain/relationship/envVar delete
            TenantServiceEnv.objects.filter(service_id=service.service_id).delete()
            TenantServiceAuth.objects.filter(service_id=service.service_id).delete()
            ServiceDomain.objects.filter(service_id=service.service_id).delete()
            TenantServiceRelation.objects.filter(service_id=service.service_id).delete()
            TenantServiceEnvVar.objects.filter(service_id=service.service_id).delete()
            TenantServiceMountRelation.objects.filter(service_id=service.service_id).delete()
            TenantServicesPort.objects.filter(service_id=service.service_id).delete()
            TenantServiceVolume.objects.filter(service_id=service.service_id).delete()
            monitorhook.serviceMonitor(username, service, 'app_delete', True)
            logger.debug("openapi.services", "delete service.result:success")
            return 200, True, u"删除成功"
        except Exception as e:
            logger.exception("openapi.services", e)
            logger.debug("openapi.services", "delete service.result:failure")
            return 412, False, u"删除失败"

    def domain_service(self, action, service, domain_name, tenant_name, username):
        try:
            if action == "start":
                domainNum = ServiceDomain.objects.filter(domain_name=domain_name).count()
                if domainNum > 0:
                    return 410, False, "域名已经存在"

                num = ServiceDomain.objects.filter(service_id=service.service_id).count()
                old_domain_name = "goodrain"
                if num == 0:
                    domain = {}
                    domain["service_id"] = service.service_id
                    domain["service_name"] = service.service_alias
                    domain["domain_name"] = domain_name
                    domain["create_time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    domaininfo = ServiceDomain(**domain)
                    domaininfo.save()
                else:
                    domain = ServiceDomain.objects.get(service_id=service.service_id)
                    old_domain_name = domain.domain_name
                    domain.domain_name = domain_name
                    domain.save()
                data = {}
                data["service_id"] = service.service_id
                data["new_domain"] = domain_name
                data["old_domain"] = old_domain_name
                data["pool_name"] = tenant_name + "@" + service.service_alias + ".Pool"
                regionClient.addUserDomain(service.service_region, json.dumps(data))
                monitorhook.serviceMonitor(username, service, 'domain_add', True)
            elif action == "close":
                servicerDomain = ServiceDomain.objects.get(service_id=service.service_id)
                data = {}
                data["service_id"] = servicerDomain.service_id
                data["domain"] = servicerDomain.domain_name
                data["pool_name"] = tenant_name + "@" + service.service_alias + ".Pool"
                regionClient.deleteUserDomain(service.service_region, json.dumps(data))
                ServiceDomain.objects.filter(service_id=service.service_id).delete()
                monitorhook.serviceMonitor(username, service, 'domain_delete', True)
            return 200, True, "success"
        except Exception as e:
            logger.exception("openapi.services", e)
            monitorhook.serviceMonitor(username, service, 'domain_manage', False)
            return 411, False, "操作失败"

    def query_domain(self, service):
        domain_list = ServiceDomain.objects.filter(service_id=service.service_id)
        if len(domain_list) > 0:
            return [x.domain_name for x in domain_list]
        else:
            return []

    def stop_service(self, service, username):
        try:
            body = {}
            body["operator"] = str(username)
            regionClient.stop(service.service_region, service.service_id, json.dumps(body))
            monitorhook.serviceMonitor(username, service, 'app_stop', True)
            return 200, True, "success"
        except Exception as e:
            logger.exception("openapi.services", e)
            monitorhook.serviceMonitor(username, service, 'app_stop', False)
            return 409, False, "停止服务失败"

    def start_service(self, tenant, service, username):
        try:
            # calculate resource
            diff_memory = service.min_node * service.min_memory
            rt_type, flag = self.predict_next_memory(tenant, service, diff_memory, False)
            if not flag:
                if rt_type == "memory":
                    return 410, False, "内存不足"
                else:
                    return 411, False, "余额不足"

            body = {}
            body["deploy_version"] = service.deploy_version
            body["operator"] = str(username)
            regionClient.restart(service.service_region, service.service_id, json.dumps(body))
            monitorhook.serviceMonitor(username, service, 'app_start', True)
            return 200, True, "success"
        except Exception as e:
            logger.exception("openapi.services", e)
            monitorhook.serviceMonitor(username, service, 'app_start', False)
            return 412, False, "启动失败"
    
    def status_service(self, service):
        result = {}
        try:
            if service.deploy_version is None or service.deploy_version == "":
                result["totalMemory"] = 0
                result["status"] = "undeploy"
                return 200, True, result
            else:
                body = regionClient.check_service_status(service.service_region, service.service_id)
                status = body[service.service_id]
                if status == "running":
                    result["totalMemory"] = service.min_node * service.min_memory
                else:
                    result["totalMemory"] = 0
                result["status"] = status
            return 200, True, result
        except Exception as e:
            logger.exception("openapi.services", e)
            logger.debug(service.service_region + "-" + service.service_id + " check_service_status is error")
            result["totalMemory"] = 0
            result['status'] = "failure"
            return 409, False, result

    def predict_next_memory(self, tenant, cur_service, newAddMemory, ischeckStatus):
        result = True
        rt_type = "memory"
        if self.MODULES["Memory_Limit"]:
            result = False
            if ischeckStatus:
                newAddMemory = newAddMemory + self.curServiceMemory(cur_service)
            if tenant.pay_type == "free":
                tm = self.calculate_real_used_resource(tenant) + newAddMemory
                logger.debug(tenant.tenant_id + " used memory " + str(tm))
                if tm <= tenant.limit_memory:
                    result = True
            elif tenant.pay_type == "payed":
                tm = self.calculate_real_used_resource(tenant) + newAddMemory
                guarantee_memory = self.calculate_real_used_resource(tenant)
                logger.debug(tenant.tenant_id + " used memory:" + str(tm) + " guarantee_memory:" + str(guarantee_memory))
                if tm - guarantee_memory <= 102400:
                    ruleJson = self.feerule[cur_service.service_region]
                    unit_money = 0
                    if tenant.pay_level == "personal":
                        unit_money = float(ruleJson['personal_money'])
                    elif tenant.pay_level == "company":
                        unit_money = float(ruleJson['company_money'])
                    total_money = unit_money * (tm * 1.0 / 1024)
                    logger.debug(tenant.tenant_id + " use memory " + str(tm) + " used money " + str(total_money))
                    if tenant.balance >= total_money:
                        result = True
                    else:
                        rt_type = "money"
            elif tenant.pay_type == "unpay":
                result = True
        return rt_type, result

    def addServicePort(self, service, is_init_account, container_port=0, protocol='', port_alias='', is_inner_service=False, is_outer_service=False):
        port = TenantServicesPort(tenant_id=service.tenant_id, service_id=service.service_id, container_port=container_port,
                                  protocol=protocol, port_alias=port_alias, is_inner_service=is_inner_service,
                                  is_outer_service=is_outer_service)
        try:
            env_prefix = port_alias.upper() if bool(port_alias) else service.service_key.upper()
            if is_inner_service:
                mapping_port = self.prepare_mapping_port(service, container_port)
                port.mapping_port = mapping_port
                self.saveServiceEnvVar(service.tenant_id, service.service_id, container_port, u"连接地址", env_prefix + "_HOST", "127.0.0.1", False, scope="outer")
                self.saveServiceEnvVar(service.tenant_id, service.service_id, container_port, u"端口", env_prefix + "_PORT", mapping_port, False, scope="outer")
            if is_init_account:
                password = service.service_id[:8]
                TenantServiceAuth.objects.create(service_id=service.service_id, user="admin", password=password)
                self.saveServiceEnvVar(service.tenant_id, service.service_id, container_port, u"用户名", env_prefix + "_USER", "admin", False, scope="both")
                self.saveServiceEnvVar(service.tenant_id, service.service_id, container_port, u"密码", env_prefix + "_PASS", password, False, scope="both")
            port.save()
        except Exception as e:
            logger.exception("openapi.services", e)

    def saveServiceEnvVar(self, tenant_id, service_id, container_port, name, attr_name, attr_value, isChange, scope="outer"):
        tenantServiceEnvVar = {}
        tenantServiceEnvVar["tenant_id"] = tenant_id
        tenantServiceEnvVar["service_id"] = service_id
        tenantServiceEnvVar['container_port'] = container_port
        tenantServiceEnvVar["name"] = name
        tenantServiceEnvVar["attr_name"] = attr_name
        tenantServiceEnvVar["attr_value"] = attr_value
        tenantServiceEnvVar["is_change"] = isChange
        tenantServiceEnvVar["scope"] = scope
        TenantServiceEnvVar(**tenantServiceEnvVar).save()

    def curServiceMemory(self, cur_service):
        memory = 0
        try:
            body = regionClient.check_service_status(cur_service.service_region, cur_service.service_id)
            status = body[cur_service.service_id]
            if status != "running":
                memory = cur_service.min_node * cur_service.min_memory
        except Exception as e:
            logger.exception("openapi.services", e)
        return memory

    def calculate_real_used_resource(self, tenant):
        totalMemory = 0
        tenant_region_list = TenantRegionInfo.objects.filter(tenant_id=tenant.tenant_id, is_active=True)
        running_data = {}
        for tenant_region in tenant_region_list:
            logger.debug(tenant_region.region_name)
            temp_data = regionClient.getTenantRunningServiceId(tenant_region.region_name, tenant_region.tenant_id)
            logger.debug(temp_data)
            if len(temp_data["data"]) > 0:
                running_data.update(temp_data["data"])
        logger.debug(running_data)
        dsn = BaseConnection()
        query_sql = '''select service_id, (s.min_node * s.min_memory) as apply_memory, total_memory  from tenant_service s where s.tenant_id = "{tenant_id}"'''.format(tenant_id=tenant.tenant_id)
        sqlobjs = dsn.query(query_sql)
        if sqlobjs is not None and len(sqlobjs) > 0:
            for sqlobj in sqlobjs:
                service_id = sqlobj["service_id"]
                apply_memory = sqlobj["apply_memory"]
                total_memory = sqlobj["total_memory"]
                disk_storage = total_memory - int(apply_memory)
                if disk_storage < 0:
                    disk_storage = 0
                real_memory = running_data.get(service_id)
                if real_memory is not None and real_memory != "":
                    totalMemory = totalMemory + int(apply_memory) + disk_storage
                else:
                    totalMemory = totalMemory + disk_storage
        return totalMemory

    def create_tenant(self, tenant_name, region, user_id, nick_name):
        """创建租户"""
        # 根据资源是否首先判断公有云、私有云注册
        # todo 暂时解决方案,后续需根据数据中心配置修改
        expired_day = 7
        if hasattr(settings, "TENANT_VALID_TIME"):
            expired_day = int(settings.TENANT_VALID_TIME)
        expired_time = datetime.datetime.now() + datetime.timedelta(d=expired_day)
            
        if settings.MODULES["Memory_Limit"]:
            tenant = Tenants.objects.create(
                tenant_name=tenant_name,
                pay_type='free',
                creater=user_id,
                region=region,
                expired_time=expired_time)
        else:
            tenant = Tenants.objects.create(
                tenant_name=tenant_name,
                pay_type='payed',
                pay_level='company',
                creater=user_id,
                region=region,
                expired_time=expired_time)
        #
        user = Users()
        user.nick_name = nick_name
        user.user_id = user_id
        monitorhook.tenantMonitor(tenant, user, "create_tenant", True)

        try:
            TenantRegionInfo.objects.create(tenant_id=tenant.tenant_id,
                                            region_name=tenant.region)
        except Exception as e:
            logger.exception("openapi.services", e)

        # 发送请求到对应的数据中心创建租户
        tenantRegionService.init_for_region(tenant.region,
                                            tenant_name,
                                            tenant.tenant_id, user)
        return tenant

    def create_service_mnt(self, tenant_id, service_id, dest_path, src_path, region):
        task = {}
        task["dep_service_id"] = "outer"
        task["tenant_id"] = tenant_id
        if dest_path:
            if dest_path.startswith("/"):
                task["mnt_name"] = "/mnt" + dest_path
            else:
                task["mnt_name"] = "/mnt/" + dest_path
        else:
            task["mnt_name"] = "/mnt/nodata"
        task["mnt_dir"] = src_path
        regionClient.createServiceMnt(region, service_id, json.dumps(task))
        tsr = TenantServiceMountRelation()
        tsr.tenant_id = tenant_id
        tsr.service_id = service_id
        tsr.dep_service_id = "outer"
        tsr.mnt_name = task["mnt_name"]
        tsr.mnt_dir = src_path
        tsr.dep_order = 0
        tsr.save()

    def add_service_extend(self, new_service, service_info):
        ports = AppServicePort.objects.filter(service_key=service_info.service_key, app_version=service_info.version)
        envs = AppServiceEnv.objects.filter(service_key=service_info.service_key, app_version=service_info.version)
        volumes = AppServiceVolume.objects.filter(service_key=service_info.service_key, app_version=service_info.version)
        for port in ports:
            self.addServicePort(new_service,
                                service_info.is_init_accout,
                                container_port=port.container_port,
                                protocol=port.protocol,
                                port_alias=port.port_alias,
                                is_inner_service=port.is_inner_service,
                                is_outer_service=port.is_outer_service)
        for env in envs:
            self.saveServiceEnvVar(new_service.tenant_id,
                                   new_service.service_id,
                                   env.container_port,
                                   env.name,
                                   env.attr_name,
                                   env.attr_value,
                                   env.is_change,
                                   env.scope)
        for volume in volumes:
            self.add_volume_list(new_service, volume.volume_path)

    def save_mnt_volume(self, service, host_path, volume_path):
        try:
            category = service.category
            region = service.service_region
            tenant_id = service.tenant_id
            service_id = service.service_id
            volume = TenantServiceVolume(service_id=service_id,
                                         category=category)
            volume.host_path = host_path
            volume.volume_path = volume_path
            volume.save()
            return volume.ID
        except Exception as e:
            logger.exception("openapi.services", e)

    def add_volume_list(self, service, volume_path):
        try:
            category = service.category
            region = service.service_region
            tenant_id = service.tenant_id
            service_id = service.service_id
            volume = TenantServiceVolume(service_id=service_id,
                                         category=category)
            # 确定host_path
            if (region == "ucloud-bj-1" or region == "ali-sh") and service.service_type == "mysql":
                host_path = "/app-data/tenant/{0}/service/{1}{2}".format(tenant_id, service_id, volume_path)
            else:
                host_path = "/grdata/tenant/{0}/service/{1}{2}".format(tenant_id, service_id, volume_path)
            volume.host_path = host_path
            volume.volume_path = volume_path
            volume.save()
            return host_path, volume.ID
        except Exception as e:
            logger.exception("openapi.services", e)
            
    def save_mnt_volume(self, service, host_path, volume_path):
        try:
            category = service.category
            region = service.service_region
            tenant_id = service.tenant_id
            service_id = service.service_id
            volume = TenantServiceVolume(service_id=service_id,
                                         category=category)
            volume.host_path = host_path
            volume.volume_path = volume_path
            volume.save()
            return volume.ID
        except Exception as e:
            logger.exception("openapi.services", e)

    def cancel_service_volume(self, service, volume_id):
        # 发送到region进行删除
        region = service.service_region
        service_id = service.service_id
        try:
            volume = TenantServiceVolume.objects.get(pk=volume_id)
        except TenantServiceVolume.DoesNotExist:
            return True
        json_data = {
            "service_id": service_id,
            "category": volume.category,
            "host_path": volume.host_path,
            "volume_path": volume.volume_path
        }
        res, body = regionClient.cancelServiceVolume(region, service_id, json.dumps(json_data))
        if res.status == 200:
            TenantServiceVolume.objects.filter(pk=volume_id).delete()
            return True
        else:
            return False

    def download_remote_service(self, service_key, version):
        """获取远程服务信息"""
        # 请求云市数据
        all_data = {
            'service_key': service_key,
            'app_version': version,
            'cloud_assistant': sn.instance.cloud_assistant,
        }
        data = json.dumps(all_data)
        logger.debug('post service json data={}'.format(data))
        res, resp = appClient.getServiceData(body=data)
        if res.status == 200:
            json_data = json.loads(resp.data)
            service_data = json_data.get("service", None)
            if not service_data:
                logger.error("no service data!")
                return 500
            # 模版信息
            base_info = None
            update_version = 1
            try:
                base_info = ServiceInfo.objects.get(service_key=service_key, version=version)
                update_version = base_info.update_version
            except Exception:
                pass
            if base_info is None:
                base_info = ServiceInfo()
            base_info.service_key = service_data.get("service_key")
            base_info.publisher = service_data.get("publisher")
            base_info.service_name = service_data.get("service_name")
            base_info.pic = service_data.get("pic")
            base_info.info = service_data.get("info")
            base_info.desc = service_data.get("desc")
            base_info.status = service_data.get("status")
            base_info.category = service_data.get("category")
            base_info.is_service = service_data.get("is_service")
            base_info.is_web_service = service_data.get("is_web_service")
            base_info.version = service_data.get("version")
            base_info.update_version = update_version
            base_info.image = service_data.get("image")
            base_info.slug = service_data.get("slug")
            base_info.extend_method = service_data.get("extend_method")
            base_info.cmd = service_data.get("cmd")
            base_info.setting = service_data.get("setting")
            base_info.env = service_data.get("env")
            base_info.dependecy = service_data.get("dependecy")
            base_info.min_node = service_data.get("min_node")
            base_info.min_cpu = service_data.get("min_cpu")
            base_info.min_memory = service_data.get("min_memory")
            base_info.inner_port = service_data.get("inner_port")
            base_info.volume_mount_path = service_data.get("volume_mount_path")
            base_info.service_type = service_data.get("service_type")
            base_info.is_init_accout = service_data.get("is_init_accout")
            base_info.namespace = service_data.get("namespace")
            base_info.save()
            logger.debug('---add app service---ok---')
            # 保存service_env
            pre_list = json_data.get('pre_list', None)
            suf_list = json_data.get('suf_list', None)
            env_list = json_data.get('env_list', None)
            port_list = json_data.get('port_list', None)
            extend_list = json_data.get('extend_list', None)
            volume_list = json_data.get('volume_list', None)
            # 新增环境参数
            env_data = []
            if env_list:
                for env in env_list:
                    app_env = AppServiceEnv(service_key=env.get("service_key"),
                                            app_version=env.get("app_version"),
                                            name=env.get("name"),
                                            attr_name=env.get("attr_name"),
                                            attr_value=env.get("attr_value"),
                                            scope=env.get("scope"),
                                            is_change=env.get("is_change"),
                                            container_port=env.get("container_port"))
                    env_data.append(app_env)
            AppServiceEnv.objects.filter(service_key=service_key, app_version=version).delete()
            if len(env_data) > 0:
                AppServiceEnv.objects.bulk_create(env_data)
            logger.debug('---add app service env---ok---')
            # 端口信息
            port_data = []
            if port_list:
                for port in port_list:
                    app_port = AppServicePort(service_key=port.get("service_key"),
                                              app_version=port.get("app_version"),
                                              container_port=port.get("container_port"),
                                              protocol=port.get("protocol"),
                                              port_alias=port.get("port_alias"),
                                              is_inner_service=port.get("is_inner_service"),
                                              is_outer_service=port.get("is_outer_service"))
                    port_data.append(app_port)
            AppServicePort.objects.filter(service_key=service_key, app_version=version).delete()
            if len(port_data) > 0:
                AppServicePort.objects.bulk_create(port_data)
            logger.debug('---add app service port---ok---')
            # 扩展信息
            extend_data = []
            if extend_list:
                for extend in extend_list:
                    app_port = ServiceExtendMethod(service_key=extend.get("service_key"),
                                                   app_version=extend.get("app_version"),
                                                   min_node=extend.get("min_node"),
                                                   max_node=extend.get("max_node"),
                                                   step_node=extend.get("step_node"),
                                                   min_memory=extend.get("min_memory"),
                                                   max_memory=extend.get("max_memory"),
                                                   step_memory=extend.get("step_memory"),
                                                   is_restart=extend.get("is_restart"))
                    extend_data.append(app_port)
            ServiceExtendMethod.objects.filter(service_key=service_key, app_version=version).delete()
            if len(extend_data) > 0:
                ServiceExtendMethod.objects.bulk_create(extend_data)
            logger.debug('---add app service extend---ok---')
            # 服务依赖关系
            relation_data = []
            if pre_list:
                for relation in pre_list:
                    app_relation = AppServiceRelation(service_key=relation.get("service_key"),
                                                      app_version=relation.get("app_version"),
                                                      app_alias=relation.get("app_alias"),
                                                      dep_service_key=relation.get("dep_service_key"),
                                                      dep_app_version=relation.get("dep_app_version"),
                                                      dep_app_alias=relation.get("dep_app_alias"))
                    relation_data.append(app_relation)
            if suf_list:
                for relation in suf_list:
                    app_relation = AppServiceRelation(service_key=relation.get("service_key"),
                                                      app_version=relation.get("app_version"),
                                                      app_alias=relation.get("app_alias"),
                                                      dep_service_key=relation.get("dep_service_key"),
                                                      dep_app_version=relation.get("dep_app_version"),
                                                      dep_app_alias=relation.get("dep_app_alias"))
                    relation_data.append(app_relation)
            AppServiceRelation.objects.filter(service_key=service_key, app_version=version).delete()
            if len(relation_data) > 0:
                AppServiceRelation.objects.bulk_create(relation_data)
            logger.debug('---add app service relation---ok---')
            # 服务持久化记录
            volume_data = []
            if volume_list:
                for app_volume in volume_list:
                    volume = AppServiceVolume(service_key=app_volume.service_key,
                                              app_version=app_volume.app_version,
                                              category=app_volume.category,
                                              volume_path=app_volume.volume_path);

                    volume_data.append(volume)
            AppServiceVolume.objects.filter(service_key=service_key, app_version=version).delete()
            if len(volume_data) > 0:
                AppServiceVolume.objects.bulk_create(volume_data)
            logger.debug('---add app service volume---ok---')

            self.downloadImage(base_info)
            return 200
        else:
            return 501

    def downloadImage(self, base_info):
        try:
            download_task = {}
            if base_info.is_slug():
                download_task = {"action": "download_and_deploy", "app_key": base_info.service_key, "app_version":base_info.version, "namespace":base_info.namespace}
                for region in RegionInfo.valid_regions():
                    logger.info(region)
                    regionClient.send_task(region, 'app_slug', json.dumps(download_task))
            else:
                download_task = {"action": "download_and_deploy", "image": base_info.image, "namespace":base_info.namespace}
                for region in RegionInfo.valid_regions():
                    regionClient.send_task(region, 'app_image', json.dumps(download_task))
        except Exception as e:
            logger.exception(e)

    def restart_service(self, tenant, service, username):
        diff_memory = service.min_node * service.min_memory
        rt_type, flag = self.predict_next_memory(tenant, service, diff_memory, False)
        if not flag:
            if rt_type == "memory":
                return 410, False, "内存不足"
            else:
                return 411, False, "余额不足"

        # stop service
        code, is_success, msg = self.stop_service(service, username)
        if code == 200:
            code, is_success, msg = self.start_service(tenant, service, username)
        return code, is_success, msg

    def update_service_memory(self, tenant, service, username, memory, limit=True):
        cpu = 20 * (int(memory) / 128)
        old_cpu = service.min_cpu
        old_memory = service.min_memory
        if int(memory) != old_memory or cpu != old_cpu:
            left = memory % 128
            if memory > 0 and left <= 65536 and left == 0:
                # calculate resource
                diff_memory = memory - int(old_memory)
                if limit:
                    rt_type, flag = self.predict_next_memory(tenant, service, diff_memory, True)
                    if not flag:
                        if rt_type == "memory":
                            return 410, False, "内存不足"
                        else:
                            return 411, False, "余额不足"

                body = {
                    "container_memory": memory,
                    "deploy_version": service.deploy_version,
                    "container_cpu": cpu,
                    "operator": username,
                }
                # body["container_memory"] = memory
                # body["deploy_version"] = service.deploy_version
                # body["container_cpu"] = cpu
                # body["operator"] = username
                regionClient.verticalUpgrade(service.service_region,
                                             service.service_id,
                                             json.dumps(body))
                # 更新console记录
                service.min_cpu = cpu
                service.min_memory = memory
                service.save()
                # 添加记录
                monitorhook.serviceMonitor(username, service, 'app_vertical', True)
        return 200, True, "success"

    def update_service_node(self, tenant, service, username, node_num, limit=True):
        new_node_num = int(node_num)
        old_min_node = service.min_node
        if new_node_num >= 0 and new_node_num != old_min_node:
            # calculate resource
            diff_memory = (new_node_num - old_min_node) * service.min_memory
            if limit:
                rt_type, flag = self.predict_next_memory(tenant, service, diff_memory, True)
                if not flag:
                    if rt_type == "memory":
                        return 410, False, "内存不足"
                    else:
                        return 411, False, "余额不足"
            body = {
                "node_num": new_node_num,
                "deploy_version": service.deploy_version,
                "operator": username,
            }
            regionClient.horizontalUpgrade(service.service_region,
                                           service.service_id,
                                           json.dumps(body))
            service.min_node = new_node_num
            service.save()
            monitorhook.serviceMonitor(username, service, 'app_horizontal', True)
        return 200, True, "success"

    def update_service_version(self, service):
        service_key = service.service_key
        version = service.version
        base_service = ServiceInfo.objects.get(service_key=service_key, version=version)
        if base_service.update_version != service.update_version:
            regionClient.update_service(service.service_region,
                                        service.service_id,
                                        {"image": base_service.image})
            service.image = base_service.image
            service.update_version = base_service.update_version
            service.save()
        return 200, True, "success"

    def download_service(self, service_key, version):
        # 从服务模版中查询依赖信息
        num = ServiceInfo.objects.filter(service_key=service_key, version=version).count()
        if num == 0:
            # 下载模版
            dep_code = self.download_remote_service(service_key, version)
            if dep_code == 500 or dep_code == 501:
                return 500, False, None, "下载{0}:{1}失败".format(service_key, version)
        # 下载依赖服务
        relation_list = AppServiceRelation.objects.filter(service_key=service_key, app_version=version)
        result_list = list(relation_list)
        dep_map = {}
        for relation in result_list:
            dep_key = relation.dep_service_key
            dep_version = relation.dep_app_version
            dep_map[dep_key] = dep_version
            num = ServiceInfo.objects.filter(service_key=dep_key, version=dep_version).count()
            if num == 0:
                status, success, tmp_map, msg = self.download_service(dep_key, dep_version)
                # 检查返回的数据
                if tmp_map is not None:
                    dep_map = dict(dep_map, **tmp_map)
                if status == 500:
                    return 500, False, None, "下载{0}:{1}失败".format(service_key, version)

        return 200, True, dep_map, "success"

    def create_service_dependency(self, tenant_id, service_id, dep_service_id, region):
        dependS = TenantServiceInfo.objects.get(service_id=dep_service_id)
        task = {}
        task["dep_service_id"] = dep_service_id
        task["tenant_id"] = tenant_id
        task["dep_service_type"] = dependS.service_type
        regionClient.createServiceDependency(region, service_id, json.dumps(task))
        tsr = TenantServiceRelation()
        tsr.tenant_id = tenant_id
        tsr.service_id = service_id
        tsr.dep_service_id = dep_service_id
        tsr.dep_service_type = dependS.service_type
        tsr.dep_order = 0
        tsr.save()

